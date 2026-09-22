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
STATUS_LABELS = {
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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status_label"] = STATUS_LABELS.get(self.status, self.status)
        d["steps"] = [{"key": s, "label": STATUS_LABELS[s],
                       "done": STATUSES.index(s) <= STATUSES.index(self.status)}
                      for s in STATUSES]
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
