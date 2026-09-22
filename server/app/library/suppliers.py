"""Stage 9 - the supplier abstraction (brief section 19).

Who actually puts bricks in a box is a business decision that will change,
possibly more than once, and possibly per order.  So nothing upstream names a
supplier: pricing asks a ``Supplier`` for a quote, fulfilment asks one to
accept an order, and swapping either is registering a different class here.

Three are stubbed out because the brief names three routes -- compatible
third-party bricks, a custom brick supplier, an outside fulfilment house.
Only the first is wired up; the other two exist so that wiring them up later
is a credentials change, not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Quote:
    supplier: str
    currency: str
    parts_cost: float           # what the bricks cost us
    packaging_cost: float
    handling_cost: float
    lead_time_days: int
    unavailable: list           # BOM lines the supplier cannot fill
    per_part: dict              # part_id -> unit cost actually quoted

    @property
    def total_cost(self) -> float:
        return round(self.parts_cost + self.packaging_cost + self.handling_cost, 2)

    def to_dict(self) -> dict:
        return {"supplier": self.supplier, "currency": self.currency,
                "parts_cost": round(self.parts_cost, 2),
                "packaging_cost": round(self.packaging_cost, 2),
                "handling_cost": round(self.handling_cost, 2),
                "total_cost": self.total_cost,
                "lead_time_days": self.lead_time_days,
                "unavailable": self.unavailable}


class Supplier:
    """What every supplier must be able to do."""

    key = "abstract"
    name = "Abstract supplier"
    currency = "ILS"

    def quote(self, lines: list, weight_g: float) -> Quote:
        raise NotImplementedError

    def can_fulfil(self, lines: list) -> bool:
        return not self.quote(lines, 0.0).unavailable

    def place_order(self, order_id: str, lines: list) -> dict:
        raise NotImplementedError


class CompatibleBrickSupplier(Supplier):
    """Option A: LEGO-compatible third-party elements, bought in bulk.

    Costs come from the brick library's own per-element figures, with a bulk
    discount that kicks in on the large counts a mosaic-scale model needs.
    """

    key = "compatible"
    name = "LEGO-compatible bricks (third party)"

    def __init__(self, markup: float = 1.0, box_cost: float = 9.5,
                 handling: float = 12.0, lead_time_days: int = 5):
        self.markup = markup
        self.box_cost = box_cost
        self.handling = handling
        self.lead_time_days = lead_time_days

    def quote(self, lines: list, weight_g: float) -> Quote:
        total = 0.0
        per_part = {}
        for l in lines:
            unit = l.unit_cost * self.markup * self._bulk(l.quantity)
            per_part[l.part_id] = round(unit, 4)
            total += unit * l.quantity
        packaging = self.box_cost + max(0.0, weight_g - 400) / 1000.0 * 4.0
        return Quote(self.name, self.currency, total, packaging, self.handling,
                     self.lead_time_days, [], per_part)

    def _bulk(self, qty: int) -> float:
        if qty >= 200:
            return 0.72
        if qty >= 50:
            return 0.85
        if qty >= 20:
            return 0.93
        return 1.0

    def place_order(self, order_id: str, lines: list) -> dict:
        # A real integration posts to the supplier's API here.  Until one is
        # configured, an order is accepted and marked for manual picking, so
        # the rest of the flow can be exercised end to end.
        return {"supplier": self.key, "reference": "PICK-%s" % order_id[:8].upper(),
                "status": "queued", "manual": True}


class CustomBrickSupplier(Supplier):
    """Option B: our own moulded elements.  Not yet contracted."""

    key = "custom"
    name = "Custom brick supplier"

    def quote(self, lines: list, weight_g: float) -> Quote:
        raise SupplierNotConfigured(self.key)

    def place_order(self, order_id: str, lines: list) -> dict:
        raise SupplierNotConfigured(self.key)


class ExternalFulfilment(Supplier):
    """Option C: someone else picks, packs and ships.  Not yet contracted."""

    key = "external"
    name = "External fulfilment provider"

    def quote(self, lines: list, weight_g: float) -> Quote:
        raise SupplierNotConfigured(self.key)

    def place_order(self, order_id: str, lines: list) -> dict:
        raise SupplierNotConfigured(self.key)


class SupplierNotConfigured(RuntimeError):
    def __init__(self, key: str):
        super().__init__("supplier %r has no credentials configured" % key)
        self.key = key


REGISTRY = {s.key: s for s in (CompatibleBrickSupplier(),
                               CustomBrickSupplier(),
                               ExternalFulfilment())}
DEFAULT_SUPPLIER = "compatible"


def get_supplier(key: str | None = None) -> Supplier:
    return REGISTRY[key or DEFAULT_SUPPLIER]
