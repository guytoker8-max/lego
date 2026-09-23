"""Taking the money, without ever touching a card.

The customer pays on the provider's own hosted page.  We send them there with
an amount we computed from the parts list, and we believe they paid only when
the provider says so -- through a signed webhook, or by asking the provider
directly when they come back.  No card number, expiry or CVC passes through
this server at any point, which keeps it out of PCI scope entirely.

Two providers:

* ``StripeCheckout`` when ``STRIPE_SECRET_KEY`` is set.  Plain HTTPS calls to
  Stripe's REST API; no SDK, nothing else to install.
* ``TestPayment`` otherwise.  It exists so the whole flow -- approve, pay,
  supplier order, tracking -- can be walked through before a Stripe account
  exists.  It says "test mode" on every screen it touches and charges nobody.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse


class PaymentError(RuntimeError):
    pass


class PaymentProvider:
    key = "abstract"
    live = False

    def create(self, order, *, product_name: str, success_url: str,
               cancel_url: str) -> dict:
        raise NotImplementedError

    def verify(self, reference: str) -> dict | None:
        """{'order_id', 'amount_minor', 'currency', 'reference'} if paid."""
        raise NotImplementedError

    def parse_webhook(self, payload: bytes, headers: dict) -> dict | None:
        raise NotImplementedError

    def refund(self, payment: dict) -> dict:
        raise NotImplementedError

    def public(self) -> dict:
        return {"provider": self.key, "live": self.live}


def minor_units(amount: float) -> int:
    """Shekels to agorot, exactly: never let a float decide a price."""
    return int(round(float(amount) * 100))


class TestPayment(PaymentProvider):
    key = "test"
    live = False

    def create(self, order, *, product_name: str, success_url: str,
               cancel_url: str) -> dict:
        return {"provider": self.key, "reference": "test_%s" % order.id[:12],
                "redirect_url": "/checkout/test/%s?token=%s"
                                % (order.id, order.access_token),
                "test_mode": True}

    def verify(self, reference: str) -> dict | None:
        return None                         # confirmed only by the test page

    def parse_webhook(self, payload: bytes, headers: dict) -> dict | None:
        return None

    def refund(self, payment: dict) -> dict:
        return {"refunded": True, "test_mode": True}


class StripeCheckout(PaymentProvider):
    key = "stripe"
    API = "https://api.stripe.com/v1"

    def __init__(self, secret_key: str, webhook_secret: str = "",
                 client=None):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.live = secret_key.startswith("sk_live_")
        self._client = client

    # ---- http ------------------------------------------------------------

    def _call(self, method: str, path: str, data: dict | None = None) -> dict:
        import httpx
        client = self._client or httpx
        kw = {"auth": (self.secret_key, ""), "timeout": 20.0}
        if method == "GET":
            resp = client.get(self.API + path, **kw)
        else:
            resp = client.post(self.API + path, data=data or {}, **kw)
        body = resp.json()
        if resp.status_code >= 400:
            raise PaymentError(body.get("error", {}).get("message",
                                                         "Stripe error"))
        return body

    # ---- checkout --------------------------------------------------------

    def create(self, order, *, product_name: str, success_url: str,
               cancel_url: str) -> dict:
        currency = (order.price.get("currency") or "ILS").lower()
        data = {
            "mode": "payment",
            "client_reference_id": order.id,
            "customer_email": order.email,
            "metadata[order_id]": order.id,
            "metadata[fingerprint]": order.fingerprint,
            "payment_intent_data[metadata][order_id]": order.id,
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][unit_amount]":
                minor_units(order.price["total"]),
            "line_items[0][price_data][product_data][name]": product_name,
            "line_items[0][price_data][product_data][description]":
                "%d pieces, shipping and VAT included" % order.piece_count,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "expires_at": int(time.time()) + 3600,
        }
        session = self._call("POST", "/checkout/sessions", data)
        return {"provider": self.key, "reference": session["id"],
                "redirect_url": session["url"], "test_mode": not self.live}

    def verify(self, reference: str) -> dict | None:
        session = self._call("GET", "/checkout/sessions/%s"
                             % urllib.parse.quote(reference, safe=""))
        return self._paid(session)

    def _paid(self, session: dict) -> dict | None:
        if session.get("payment_status") != "paid":
            return None
        return {"order_id": session.get("client_reference_id")
                or session.get("metadata", {}).get("order_id"),
                "amount_minor": session.get("amount_total"),
                "currency": (session.get("currency") or "").upper(),
                "reference": session.get("id"),
                "payment_intent": session.get("payment_intent")}

    # ---- webhook ---------------------------------------------------------

    def parse_webhook(self, payload: bytes, headers: dict) -> dict | None:
        """Verify Stripe's signature, then read a completed checkout."""
        if not self.webhook_secret:
            raise PaymentError("STRIPE_WEBHOOK_SECRET is not set.")
        header = headers.get("stripe-signature", "")
        if not verify_stripe_signature(payload, header, self.webhook_secret):
            raise PaymentError("Bad webhook signature.")
        event = json.loads(payload)
        if event.get("type") not in ("checkout.session.completed",
                                     "checkout.session.async_payment_succeeded"):
            return None
        return self._paid(event.get("data", {}).get("object", {}))

    def refund(self, payment: dict) -> dict:
        intent = payment.get("payment_intent")
        if not intent:
            raise PaymentError("No payment to refund.")
        r = self._call("POST", "/refunds", {"payment_intent": intent})
        return {"refunded": r.get("status") in ("succeeded", "pending"),
                "refund_id": r.get("id")}


def verify_stripe_signature(payload: bytes, header: str, secret: str,
                            tolerance: int = 300, now: float | None = None) -> bool:
    """Stripe's scheme: HMAC-SHA256 over "<timestamp>.<body>", fresh only."""
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    try:
        ts = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs((now or time.time()) - ts) > tolerance:
        return False
    expected = hmac.new(secret.encode(), b"%d." % ts + payload,
                        hashlib.sha256).hexdigest()
    sigs = [v for k, v in (p.split("=", 1) for p in header.split(",") if "=" in p)
            if k == "v1"]
    return any(hmac.compare_digest(expected, s) for s in sigs)


def provider_from_env() -> PaymentProvider:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if key:
        return StripeCheckout(key, os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    return TestPayment()
