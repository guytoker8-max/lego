"""Stage 10 - OrderService.

Everything after "Make My Set": creating the order, moving it through the
states the brief lists, and handing the picking list to whichever supplier is
configured.

Payment is deliberately not implemented here and no card detail ever reaches
this service.  ``PaymentProvider`` is an interface with one stub behind it;
connecting a real processor means adding a class, and the order flow does not
change.  Storing card data in the app is exactly what the brief rules out.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict

from ..library.suppliers import get_supplier

STATUSES = ("confirmed", "preparing", "packing", "shipped", "delivered")
# Before and beside that track.  A web order waits for payment first, and is
# only "confirmed" once the money is in and the supplier has the order.
PRE_STATUSES = ("awaiting_payment",)
END_STATUSES = ("cancelled",)
ALL_STATUSES = PRE_STATUSES + STATUSES + END_STATUSES
STATUS_LABELS = {
    "awaiting_payment": "Waiting for payment",
    "cancelled": "Cancelled",
    "confirmed": "Order confirmed",
    "preparing": "Parts being prepared",
    "packing": "Set being packed",
    "shipped": "Shipped",
    "delivered": "Delivered",
}


@dataclass
class Order:
    id: str
    model_id: str
    fingerprint: str            # ties the box to the exact model ordered
    status: str
    price: dict
    piece_count: int
    created_at: float
    history: list = field(default_factory=list)
    tracking: dict = field(default_factory=dict)
    supplier_ref: dict = field(default_factory=dict)
    # Web checkout.  All optional, so orders written before these existed
    # still load.
    email: str = ""
    ship_to: dict = field(default_factory=dict)
    shipping_method: str = ""
    payment: dict = field(default_factory=dict)
    supplier_key: str = ""
    lines: list = field(default_factory=list)      # BOM snapshot, as ordered
    approval: dict = field(default_factory=dict)   # what the customer approved
    access_token: str = ""                         # the customer's link key

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status_label"] = STATUS_LABELS.get(self.status, self.status)
        reached = (STATUSES.index(self.status) if self.status in STATUSES
                   else -1)
        d["steps"] = [{"key": s, "label": STATUS_LABELS[s],
                       "done": STATUSES.index(s) <= reached}
                      for s in STATUSES]
        return d

    def public(self) -> dict:
        """What the customer's order page may show: no token, no costs."""
        d = self.to_dict()
        d.pop("access_token", None)
        price = dict(d.get("price") or {})
        price.pop("supplier", None)
        breakdown = dict(price.get("breakdown") or {})
        for k in ("parts", "packaging", "handling", "margin"):
            breakdown.pop(k, None)
        price["breakdown"] = breakdown
        d["price"] = price
        ref = d.get("supplier_ref") or {}
        d["supplier_ref"] = {"status": ref.get("status")}
        d.pop("lines", None)
        return d


class PaymentProvider:
    """Interface only.  A real processor implements authorise/capture."""

    key = "abstract"

    def begin(self, order_id: str, amount: float, currency: str) -> dict:
        raise NotImplementedError


class DeferredPayment(PaymentProvider):
    """Stand-in until a processor is connected.

    Returns a handoff the client would redirect to.  No card detail is taken
    here, by design: when a processor is connected, this is the only class
    that changes.
    """

    key = "deferred"

    def begin(self, order_id: str, amount: float, currency: str) -> dict:
        return {
            "provider": self.key,
            "status": "awaiting_provider",
            "message": ("No payment provider is connected yet. The order is "
                        "held and can be completed once one is."),
            "amount": amount,
            "currency": currency,
            "reference": order_id,
        }


class OrderService:
    def __init__(self, store, payment: PaymentProvider | None = None,
                 supplier_key: str | None = None):
        self.store = store
        self.payment = payment or DeferredPayment()
        self.supplier_key = supplier_key

    def create(self, model_id: str, fingerprint: str, price: dict,
               piece_count: int, lines: list) -> Order:
        order = Order(
            id=uuid.uuid4().hex,
            model_id=model_id,
            fingerprint=fingerprint,
            status="confirmed",
            price=price,
            piece_count=piece_count,
            created_at=time.time(),
        )
        order.history.append({"status": "confirmed", "at": order.created_at})

        supplier = get_supplier(self.supplier_key)
        try:
            order.supplier_ref = supplier.place_order(order.id, lines)
        except Exception as exc:
            order.supplier_ref = {"error": str(exc)}

        self.store.save_order(order)
        return order

    def begin_payment(self, order: Order) -> dict:
        return self.payment.begin(order.id, order.price.get("total", 0.0),
                                  order.price.get("currency", "ILS"))

    # ---- web checkout ----------------------------------------------------
    #
    # The order is written before payment, so the payment provider has a
    # reference to hold, but nothing goes to a supplier until the money is
    # confirmed -- by the provider's webhook, or by asking the provider on
    # the customer's return.  Whichever arrives first wins; the second is a
    # no-op, which is what makes it safe to have both.

    def create_pending(self, *, model_id: str, fingerprint: str, price: dict,
                       piece_count: int, lines: list, email: str,
                       ship_to: dict, shipping_method: str, approval: dict,
                       supplier_key: str) -> Order:
        import secrets
        order = Order(
            id=uuid.uuid4().hex, model_id=model_id, fingerprint=fingerprint,
            status="awaiting_payment", price=price, piece_count=piece_count,
            created_at=time.time(), email=email, ship_to=ship_to,
            shipping_method=shipping_method, approval=approval,
            supplier_key=supplier_key,
            lines=[l.to_dict() for l in lines],
            access_token=secrets.token_urlsafe(18),
        )
        order.history.append({"status": order.status, "at": order.created_at})
        self.store.save_order(order)
        return order

    def mark_paid(self, order_id: str, payment: dict, *,
                  booklet_url: str = "") -> Order:
        """Money is in: hand the order to the supplier.  Idempotent."""
        order = self.store.get_order(order_id)
        if order.status != "awaiting_payment":
            return order
        order.payment = dict(order.payment, **payment, status="paid",
                             paid_at=time.time())
        order.status = "confirmed"
        order.history.append({"status": "confirmed", "at": time.time(),
                              "note": "payment received"})
        self._submit(order, booklet_url)
        self.store.save_order(order)
        return order

    def _submit(self, order: Order, booklet_url: str) -> None:
        from ..models import BomLine
        from ..suppliers import (ShipTo, SupplierOrderRequest, get_adapter)
        keys = BomLine.__dataclass_fields__
        lines = [BomLine(**{k: v for k, v in l.items() if k in keys})
                 for l in order.lines]
        try:
            adapter = get_adapter(order.supplier_key or self.supplier_key)
            result = adapter.create_order(SupplierOrderRequest(
                order_id=order.id, lines=lines,
                ship_to=ShipTo.from_dict(order.ship_to),
                fingerprint=order.fingerprint, booklet_url=booklet_url,
                blind_ship=True,
                packing_note="Ship in plain packaging with the enclosed "
                             "booklet. No supplier invoice or prices in the box."))
            order.supplier_ref = result.to_dict()
        except Exception as exc:
            # The customer has paid; a supplier hiccup is ours to fix, not
            # theirs to see as a failed order.  Operations sees the error.
            order.supplier_ref = {"error": str(exc), "status": "not_sent"}

    def sync_from_supplier(self, order_id: str) -> Order:
        """Pull the supplier's status and tracking onto the order."""
        from ..suppliers import get_adapter
        order = self.store.get_order(order_id)
        ref = (order.supplier_ref or {}).get("reference")
        if not ref or order.status in PRE_STATUSES + END_STATUSES:
            return order
        adapter = get_adapter(order.supplier_key or self.supplier_key)
        status = adapter.get_order_status(ref)
        mapped = {"received": "confirmed", "in_production": "preparing",
                  "packed": "packing", "shipped": "shipped",
                  "delivered": "delivered"}.get(status)
        tracking = adapter.get_tracking(ref)
        if tracking:
            order.tracking = tracking.to_dict()
        order.supplier_ref = dict(order.supplier_ref, status=status)
        if mapped and STATUSES.index(mapped) > STATUSES.index(order.status):
            order.status = mapped
            order.history.append({"status": mapped, "at": time.time(),
                                  "note": "from supplier"})
        self.store.save_order(order)
        return order

    def cancel(self, order_id: str, reason: str = "") -> Order:
        from ..suppliers import get_adapter
        order = self.store.get_order(order_id)
        if order.status in ("shipped", "delivered", "cancelled"):
            raise ValueError("An order that has %s cannot be cancelled."
                             % order.status)
        ref = (order.supplier_ref or {}).get("reference")
        if ref:
            try:
                get_adapter(order.supplier_key or self.supplier_key) \
                    .cancel_order(ref)
            except Exception as exc:
                order.supplier_ref = dict(order.supplier_ref,
                                          cancel_error=str(exc))
        order.status = "cancelled"
        order.history.append({"status": "cancelled", "at": time.time(),
                              "note": reason})
        self.store.save_order(order)
        return order

    def advance(self, order_id: str, status: str) -> Order:
        if status not in STATUSES:
            raise ValueError("unknown order status: %r" % status)
        order = self.store.get_order(order_id)
        order.status = status
        order.history.append({"status": status, "at": time.time()})
        if status == "shipped" and not order.tracking:
            order.tracking = {"carrier": "Israel Post",
                              "number": "BS%s" % order.id[:10].upper(),
                              "url": ""}
        self.store.save_order(order)
        return order
