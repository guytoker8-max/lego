"""Suppliers without an API: a price list in, a purchase order out.

Most wholesalers, bulk sellers and custom moulders sell this way.  They send
a price list (or quote one), and take orders by email, spreadsheet or a web
portal.  This adapter is that, made precise:

* ``calculate_cost`` prices a parts list from the supplier's own price list,
  translated into their part numbers.  With no price list loaded it refuses
  to quote rather than guessing a number a customer would then be charged.
* ``create_order`` writes a purchase order into the ledger, in the supplier's
  SKUs, marked for a person to send.  Status and tracking are recorded as the
  supplier replies.

The price list is a CSV with the columns
``design_id,color_id,supplier_sku,unit_cost[,stock]`` -- colour ids in our
(LDraw) numbering.  One file per supplier, pointed to by an environment
variable, so loading a real one is a deployment change and not a code change.
"""

from __future__ import annotations

import csv
import os
import time

from ..library.suppliers import Quote, SupplierNotConfigured
from .base import (Capabilities, InventoryLevel, ShipTo, SupplierAdapter,
                   SupplierOrderRequest, SupplierOrderResult, SupplierProduct,
                   Tracking)
from .ledger import PurchaseOrderLedger


class PriceListSupplier(SupplierAdapter):
    def __init__(self, key: str, name: str, ledger: PurchaseOrderLedger, *,
                 capabilities: Capabilities, currency: str = "ILS",
                 price_list_path: str = "", packaging_cost: float = 0.0,
                 handling_cost: float = 0.0, fx_to_ils: float = 1.0):
        self.key = key
        self.name = name
        self.ledger = ledger
        self.capabilities = capabilities
        self.currency = "ILS"                 # quotes are converted to ours
        self.source_currency = currency
        self.fx = fx_to_ils
        self.packaging_cost = packaging_cost
        self.handling_cost = handling_cost
        self.price_list_path = price_list_path
        self._products = None

    # ---- the price list --------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.price_list_path) and os.path.exists(self.price_list_path)

    def _load(self) -> dict:
        if self._products is not None:
            return self._products
        if not self.configured:
            raise SupplierNotConfigured(self.key)
        products = {}
        with open(self.price_list_path, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    part, color = row["design_id"].strip(), int(row["color_id"])
                    stock = row.get("stock", "").strip()
                    products[(part, color)] = SupplierProduct(
                        supplier=self.key,
                        supplier_sku=row.get("supplier_sku", "").strip() or part,
                        part_id=part, color_id=color,
                        unit_cost=round(float(row["unit_cost"]) * self.fx, 4),
                        currency=self.currency,
                        available_qty=int(stock) if stock else None,
                        lead_time_days=self.capabilities.lead_time_days)
                except (KeyError, ValueError):
                    continue                      # a bad row is skipped, not fatal
        self._products = products
        return products

    def get_products(self) -> list:
        return list(self._load().values())

    def get_product_details(self, part_id: str, color_id: int):
        return self._load().get((part_id, color_id))

    def get_inventory(self, items: list) -> list:
        products = self._load()
        out = []
        for part, color in items:
            p = products.get((part, color))
            out.append(InventoryLevel(
                part, color, available=p is not None and p.available_qty != 0,
                quantity=p.available_qty if p else 0))
        return out

    # ---- money -----------------------------------------------------------

    def calculate_cost(self, lines: list, weight_g: float,
                       ship_to: ShipTo | None = None) -> Quote:
        products = self._load()
        total, per_part, missing = 0.0, {}, []
        for l in lines:
            p = products.get((l.part_id, l.color_id))
            if p is None or (p.available_qty is not None
                             and p.available_qty < l.quantity):
                missing.append({"part_id": l.part_id, "color_id": l.color_id,
                                "part_name": l.part_name,
                                "color_name": l.color_name,
                                "needed": l.quantity})
                continue
            per_part[l.part_id] = p.unit_cost
            total += p.unit_cost * l.quantity
        return Quote(self.name, self.currency, total, self.packaging_cost,
                     self.handling_cost, self.capabilities.lead_time_days or 14,
                     missing, per_part)

    # ---- orders ----------------------------------------------------------

    def create_order(self, request: SupplierOrderRequest) -> SupplierOrderResult:
        products = self._load()
        reference = "PO-%s-%s" % (self.key.upper()[:6], request.order_id[:8].upper())
        lines = []
        for l in request.lines:
            p = products.get((l.part_id, l.color_id))
            lines.append(dict(l.to_dict(),
                              supplier_sku=p.supplier_sku if p else ""))
        self.ledger.save({
            "reference": reference, "supplier": self.key,
            "order_id": request.order_id, "status": "received",
            "created_at": time.time(), "fingerprint": request.fingerprint,
            "ship_to": request.ship_to.to_dict() if request.ship_to else None,
            "blind_ship": request.blind_ship,
            "booklet_url": request.booklet_url,
            "packing_note": request.packing_note,
            "piece_count": request.piece_count, "lines": lines,
            "send_via": self.capabilities.orders_via,
            "history": [{"status": "received", "at": time.time(),
                         "note": "purchase order written, not yet sent"}],
        })
        return SupplierOrderResult(
            supplier=self.key, reference=reference, status="received",
            manual=True,
            message="Purchase order written; send it to %s by %s."
                    % (self.name, self.capabilities.orders_via))

    def get_order_status(self, reference: str) -> str:
        po = self.ledger.get(reference)
        return po["status"] if po else "rejected"

    def get_tracking(self, reference: str):
        t = (self.ledger.get(reference) or {}).get("tracking")
        return Tracking(**t) if t else None

    def cancel_order(self, reference: str) -> bool:
        po = self.ledger.get(reference)
        if not po or po["status"] in ("shipped", "delivered", "cancelled"):
            return False
        self.ledger.advance(reference, "cancelled",
                            note="cancel with the supplier as well")
        return True
