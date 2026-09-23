"""The supplier contract every fulfilment route has to meet.

The business is dropshipping: a customer pays us, and somebody else picks the
bricks, prints the booklet and ships the box.  Who that somebody is will
change -- a wholesaler this year, a marketplace seller for a rare colour, our
own moulds one day -- so nothing outside this package may name one.  Pricing
asks an adapter what the parts cost, checkout asks it to accept an order, and
the operations screen asks it where the order has got to.

``SupplierAdapter`` extends the original ``library.suppliers.Supplier`` rather
than replacing it: ``quote`` and ``place_order`` still work, so everything
written against the first interface (the mobile app's order route, the
pricing engine, the tests) keeps working unchanged.

A supplier is also described, not just called.  ``Capabilities`` records what
is actually known about it -- whether it has an API and what that API can do,
whether it dropships, whether it ships blind -- with ``None`` for "not yet
established".  The research in ``docs/SUPPLIER_RESEARCH.md`` is where those
answers come from; an adapter must not claim more than that document can back.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from ..library.suppliers import Quote, Supplier, SupplierNotConfigured

# What a supplier-side order can be doing, in our words, whatever the supplier
# calls it.  Adapters translate their own states into these.
SUPPLIER_STATUSES = (
    "received",        # the supplier has the order (or the purchase order)
    "in_production",   # being picked / moulded / printed
    "packed",
    "shipped",
    "delivered",
    "cancelled",
    "rejected",        # the supplier refused it; a person needs to look
)


@dataclass
class Capabilities:
    api: str = "none"                  # "none" | "catalog" | "catalog+orders"
    orders_via: str = "manual"         # "api" | "email" | "portal" | "manual"
    dropship: bool | None = None       # ships to our customer's address
    blind_ship: bool | None = None     # no supplier branding or prices in the box
    prints_booklet: bool | None = None # can put our printed instructions in
    moq_pieces: int | None = None      # minimum order, in elements
    regions: tuple = ()                # where it ships from / to
    lead_time_days: int | None = None
    part_numbering: str = "bricklink"  # "bricklink" design ids, or "own"
    status: str = "research"           # "live" | "not_contracted" | "research"
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["regions"] = list(self.regions)
        return d


@dataclass
class SupplierProduct:
    """One part in one colour, as a particular supplier sells it."""

    supplier: str
    supplier_sku: str
    part_id: str               # our design id (BrickLink numbering)
    color_id: int              # our colour id (LDraw numbering)
    unit_cost: float
    currency: str
    available_qty: int | None = None   # None: the supplier does not say
    lead_time_days: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InventoryLevel:
    part_id: str
    color_id: int
    available: bool
    quantity: int | None = None
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShipTo:
    name: str
    line1: str
    city: str
    postal_code: str
    country: str               # ISO 3166-1 alpha-2
    line2: str = ""
    region: str = ""
    phone: str = ""
    email: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ShipTo | None":
        if not d:
            return None
        keys = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in keys})


@dataclass
class SupplierOrderRequest:
    """Everything a supplier needs to put the right box on the right doorstep."""

    order_id: str
    lines: list                        # BomLine, counted from the model
    ship_to: ShipTo | None = None
    fingerprint: str = ""              # the exact model these parts build
    booklet_url: str = ""              # printable instructions for the box
    blind_ship: bool = True            # our name on the slip, not theirs
    packing_note: str = ""

    @property
    def piece_count(self) -> int:
        return sum(l.quantity for l in self.lines)


@dataclass
class SupplierOrderResult:
    supplier: str
    reference: str
    status: str = "received"
    manual: bool = False               # a person has to act on it
    message: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Tracking:
    carrier: str
    number: str
    url: str = ""
    status: str = ""
    events: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class NotSupportedBySupplier(RuntimeError):
    """The supplier exists but cannot do this through any channel we have.

    Distinct from ``SupplierNotConfigured`` (credentials missing): this one
    will not go away by adding a key.
    """


class SupplierAdapter(Supplier):
    """What every fulfilment route must be able to do."""

    key = "abstract"
    name = "Abstract supplier"
    currency = "ILS"
    capabilities = Capabilities()

    # ---- catalogue -------------------------------------------------------

    def get_products(self) -> list:
        """Every part/colour this supplier can sell us, as SupplierProduct."""
        raise NotImplementedError

    def get_inventory(self, items: list) -> list:
        """Stock for ``[(part_id, color_id), ...]``, as InventoryLevel."""
        raise NotImplementedError

    def get_product_details(self, part_id: str, color_id: int):
        """One SupplierProduct, or None if the supplier does not sell it."""
        for p in self.get_products():
            if p.part_id == part_id and p.color_id == color_id:
                return p
        return None

    # ---- money -----------------------------------------------------------

    def calculate_cost(self, lines: list, weight_g: float,
                       ship_to: ShipTo | None = None) -> Quote:
        """What these parts cost us from this supplier, landed."""
        raise NotImplementedError

    # ---- orders ----------------------------------------------------------

    def create_order(self, request: SupplierOrderRequest) -> SupplierOrderResult:
        raise NotImplementedError

    def get_order_status(self, reference: str) -> str:
        """One of SUPPLIER_STATUSES."""
        raise NotImplementedError

    def get_tracking(self, reference: str) -> Tracking | None:
        raise NotImplementedError

    def cancel_order(self, reference: str) -> bool:
        """True if the supplier accepted the cancellation."""
        raise NotImplementedError

    # ---- description -----------------------------------------------------

    def describe(self) -> dict:
        return {"key": self.key, "name": self.name, "currency": self.currency,
                "capabilities": self.capabilities.to_dict()}

    # ---- the original interface, kept working ----------------------------

    def quote(self, lines: list, weight_g: float) -> Quote:
        return self.calculate_cost(lines, weight_g)

    def place_order(self, order_id: str, lines: list) -> dict:
        return self.create_order(
            SupplierOrderRequest(order_id=order_id, lines=lines)).to_dict()


__all__ = [
    "Capabilities", "SupplierProduct", "InventoryLevel", "ShipTo",
    "SupplierOrderRequest", "SupplierOrderResult", "Tracking",
    "SupplierAdapter", "NotSupportedBySupplier", "SupplierNotConfigured",
    "SUPPLIER_STATUSES", "Quote",
]
