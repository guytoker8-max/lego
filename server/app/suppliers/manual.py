"""The route that works today: we buy compatible bricks and a person ships.

This is the original ``CompatibleBrickSupplier`` -- same bulk price list, same
quote -- with the full adapter interface on top.  An order becomes a purchase
order in the ledger, marked for a person to act on: pick it from a small bulk
stock of common parts, or forward it to a wholesaler.  The operations screen
moves it along and records tracking, and the customer sees each move.

Nothing here pretends to be automated.  ``manual=True`` on every result says
so, and the order screen shows it.
"""

from __future__ import annotations

import time

from ..library import LIBRARY
from ..library.suppliers import CompatibleBrickSupplier
from .base import (Capabilities, InventoryLevel, ShipTo, SupplierAdapter,
                   SupplierOrderRequest, SupplierOrderResult, SupplierProduct,
                   Tracking)
from .ledger import PurchaseOrderLedger


def house_sku(part_id: str, color_id: int) -> str:
    return "BS-%s-%d" % (part_id, color_id)


class ManualFulfilment(SupplierAdapter, CompatibleBrickSupplier):
    key = "compatible"
    name = "LEGO-compatible bricks (manual fulfilment)"
    capabilities = Capabilities(
        api="none", orders_via="manual", dropship=True, blind_ship=True,
        prints_booklet=True, moq_pieces=None, regions=("IL",),
        lead_time_days=5, part_numbering="bricklink", status="live",
        notes=("Orders become purchase orders for a person to pick or forward "
               "to a wholesaler. Costs are the brick library's bulk estimates "
               "until a supplier's real price list is loaded."),
    )

    def __init__(self, ledger: PurchaseOrderLedger, colors=None, **kw):
        CompatibleBrickSupplier.__init__(self, **kw)
        self.ledger = ledger
        self._colors = colors

    # ---- catalogue -------------------------------------------------------

    def _color_ids(self) -> list:
        if self._colors is None:
            from ..library.colors import COMMON
            self._colors = [c.id for c in COMMON]
        return self._colors

    def get_products(self) -> list:
        out = []
        for b in LIBRARY.all():
            if b.kind == "baseplate":
                continue
            for cid in self._color_ids():
                out.append(SupplierProduct(
                    supplier=self.key, supplier_sku=house_sku(b.part_id, cid),
                    part_id=b.part_id, color_id=cid, unit_cost=b.base_cost,
                    currency=self.currency, available_qty=None,
                    lead_time_days=self.lead_time_days))
        return out

    def get_product_details(self, part_id: str, color_id: int):
        if not LIBRARY.exists(part_id) or color_id not in self._color_ids():
            return None
        b = LIBRARY.get(part_id)
        return SupplierProduct(self.key, house_sku(part_id, color_id), part_id,
                               color_id, b.base_cost, self.currency, None,
                               self.lead_time_days)

    def get_inventory(self, items: list) -> list:
        # No live stock feed: availability is the library's own flag, which
        # is where a stock file would be loaded when there is one.
        return [InventoryLevel(p, c, LIBRARY.exists(p) and LIBRARY.available(p))
                for p, c in items]

    # ---- money -----------------------------------------------------------

    def calculate_cost(self, lines: list, weight_g: float,
                       ship_to: ShipTo | None = None):
        return CompatibleBrickSupplier.quote(self, lines, weight_g)

    def quote(self, lines: list, weight_g: float):
        return self.calculate_cost(lines, weight_g)

    # ---- orders ----------------------------------------------------------

    def create_order(self, request: SupplierOrderRequest) -> SupplierOrderResult:
        reference = "PO-%s" % request.order_id[:8].upper()
        self.ledger.save({
            "reference": reference,
            "supplier": self.key,
            "order_id": request.order_id,
            "status": "received",
            "created_at": time.time(),
            "fingerprint": request.fingerprint,
            "ship_to": request.ship_to.to_dict() if request.ship_to else None,
            "blind_ship": request.blind_ship,
            "booklet_url": request.booklet_url,
            "packing_note": request.packing_note,
            "piece_count": request.piece_count,
            "lines": [dict(l.to_dict(),
                           supplier_sku=house_sku(l.part_id, l.color_id))
                      for l in request.lines],
            "history": [{"status": "received", "at": time.time(), "note": ""}],
        })
        return SupplierOrderResult(
            supplier=self.key, reference=reference, status="received",
            manual=True,
            message="Purchase order created for picking and packing.")

    def get_order_status(self, reference: str) -> str:
        po = self.ledger.get(reference)
        return po["status"] if po else "rejected"

    def get_tracking(self, reference: str):
        po = self.ledger.get(reference)
        t = (po or {}).get("tracking")
        return Tracking(**t) if t else None

    def cancel_order(self, reference: str) -> bool:
        po = self.ledger.get(reference)
        if not po or po["status"] in ("shipped", "delivered"):
            return False
        self.ledger.advance(reference, "cancelled", note="cancelled by us")
        return True
