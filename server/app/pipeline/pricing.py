"""Stage 8 - PricingEngine.

The price is computed from the bill of materials, never guessed and never
produced by a language model.  Every figure traces to something real: the
elements the model contains, what a supplier charges for them, the box, the
picking, the shipping weight, and a stated margin and VAT.

The breakdown is returned alongside the total, because a customer looking at
a four-figure number for a big mosaic deserves to see that it is 2,000 bricks
and not a markup.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..library.suppliers import Supplier, get_supplier

VAT_RATE = 0.18              # Israel, as of 2025
DEFAULT_MARGIN = 0.42        # gross margin on landed cost
CURRENCY = "ILS"
SYMBOL = "₪"


@dataclass
class ShippingOption:
    key: str
    label: str
    cost: float
    days: str


class PricingEngine:
    def __init__(self, supplier: Supplier | None = None,
                 margin: float = DEFAULT_MARGIN, vat_rate: float = VAT_RATE):
        self.supplier = supplier or get_supplier()
        self.margin = margin
        self.vat_rate = vat_rate

    def price(self, lines: list, weight_g: float,
              shipping: str = "standard") -> dict:
        quote = self.supplier.quote(lines, weight_g)
        ship = self.shipping_options(weight_g)
        chosen = next((s for s in ship if s.key == shipping), ship[0])

        landed = quote.total_cost
        before_vat = landed / (1.0 - self.margin) if self.margin < 1 else landed
        before_vat = self._round_up(before_vat)
        vat = before_vat * self.vat_rate
        total = before_vat + vat + chosen.cost

        return {
            "currency": CURRENCY,
            "symbol": SYMBOL,
            "supplier": quote.to_dict(),
            "breakdown": {
                "parts": round(quote.parts_cost, 2),
                "packaging": round(quote.packaging_cost, 2),
                "handling": round(quote.handling_cost, 2),
                "margin": round(before_vat - landed, 2),
                "subtotal": round(before_vat, 2),
                "vat": round(vat, 2),
                "shipping": round(chosen.cost, 2),
            },
            "set_price": round(before_vat + vat, 2),
            "total": round(total, 2),
            "shipping_options": [s.__dict__ for s in ship],
            "shipping_selected": chosen.key,
            "production_days": quote.lead_time_days,
            "unavailable": quote.unavailable,
        }

    def shipping_options(self, weight_g: float) -> list:
        # Sets ship straight from the supplier in China (4PX standard,
        # FedEx express), so these are its transit times to Israel, not
        # a local courier's.
        kg = max(0.3, weight_g / 1000.0)
        return [
            ShippingOption("standard", "Standard", self._round_up(18 + kg * 7),
                           "7-15 business days"),
            ShippingOption("express", "Express", self._round_up(38 + kg * 11),
                           "5-7 business days"),
            ShippingOption("pickup", "Collect in store", 0.0, "Ready when made"),
        ]

    def estimate_from_model(self, model, inventory, shipping: str = "standard") -> dict:
        lines = inventory.bill_of_materials(model)
        return self.price(lines, model.weight_g, shipping)

    @staticmethod
    def _round_up(value: float) -> float:
        """Round to the nearest 5 so prices read as prices, never downward."""
        return float(math.ceil(value / 5.0) * 5.0)
