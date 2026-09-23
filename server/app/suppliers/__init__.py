"""Fulfilment routes.  See ``base.py`` for the contract.

``configure`` builds every adapter once, at start-up, and registers them in
``library.suppliers.REGISTRY`` -- the registry the pricing engine and the
original order route already read -- so turning a supplier on is
configuration, and nothing that prices or orders needs to know which one.
"""

from __future__ import annotations

import os

from ..library import suppliers as _legacy
from .base import (SUPPLIER_STATUSES, Capabilities, InventoryLevel,
                   NotSupportedBySupplier, ShipTo, SupplierAdapter,
                   SupplierNotConfigured, SupplierOrderRequest,
                   SupplierOrderResult, SupplierProduct, Tracking)
from .bricklink import BrickLinkReference
from .ledger import PurchaseOrderLedger, purchase_order_csv
from .manual import ManualFulfilment, house_sku
from .pricelist import PriceListSupplier
from .profiles import PROFILES

LEDGER: PurchaseOrderLedger | None = None


def configure(data_dir: str) -> dict:
    """Create the adapters and make them the registry's suppliers."""
    global LEDGER
    LEDGER = PurchaseOrderLedger(data_dir)
    adapters = [ManualFulfilment(LEDGER), BrickLinkReference()]
    for p in PROFILES:
        adapters.append(PriceListSupplier(
            p["key"], p["name"], LEDGER, capabilities=p["capabilities"],
            currency=p.get("currency", "ILS"),
            price_list_path=os.environ.get(p["price_list_env"], ""),
            packaging_cost=p.get("packaging_cost", 0.0),
            handling_cost=p.get("handling_cost", 0.0),
            fx_to_ils=float(os.environ.get(p.get("fx_env", ""), 0) or
                            p.get("fx_to_ils", 1.0))))
    for a in adapters:
        _legacy.REGISTRY[a.key] = a
    return dict(_legacy.REGISTRY)


def adapters() -> list:
    return [s for s in _legacy.REGISTRY.values()
            if isinstance(s, SupplierAdapter)]


def get_adapter(key: str | None = None) -> SupplierAdapter:
    s = _legacy.get_supplier(key)
    if not isinstance(s, SupplierAdapter):
        raise SupplierNotConfigured(key or _legacy.DEFAULT_SUPPLIER)
    return s


__all__ = [
    "configure", "adapters", "get_adapter", "LEDGER", "purchase_order_csv",
    "house_sku", "SupplierAdapter", "Capabilities", "ShipTo",
    "SupplierOrderRequest", "SupplierOrderResult", "SupplierProduct",
    "InventoryLevel", "Tracking", "NotSupportedBySupplier",
    "SupplierNotConfigured", "SUPPLIER_STATUSES",
]
