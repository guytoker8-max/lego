"""BrickLink: a real API, but a seller's API.

BrickLink's Store API (OAuth 1.0a, four credentials from a seller account)
covers the catalogue, colours, the price guide, and the orders a *store
receives*.  It has no call for buying: there is no cart, no checkout, and no
way to place an order with another store.  So this adapter is useful for two
things and honest about the third:

* **Catalogue and pricing** work: part details, the colours a part exists in,
  and the price guide (what sellers are actually asking), which is the best
  public benchmark for what a part should cost.
* **Ordering** raises ``NotSupportedBySupplier``.  Buying on BrickLink is a
  person with a basket.  Registering this adapter as the fulfilment route
  would be a mistake; registering it as a price reference is the point.

See ``docs/SUPPLIER_RESEARCH.md`` for the terms that govern the data.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
import urllib.parse

from ..library import LIBRARY
from ..library.suppliers import Quote, SupplierNotConfigured
from .base import (Capabilities, InventoryLevel, NotSupportedBySupplier,
                   ShipTo, SupplierAdapter, SupplierProduct)
from .colors import LDRAW_TO_BRICKLINK, bricklink_color

API = "https://api.bricklink.com/api/store/v1"


def oauth1_header(method: str, url: str, params: dict, consumer_key: str,
                  consumer_secret: str, token: str, token_secret: str,
                  nonce: str | None = None, timestamp: str | None = None) -> str:
    """An OAuth 1.0a HMAC-SHA1 Authorization header (RFC 5849)."""
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_token": token,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_nonce": nonce or secrets.token_hex(12),
        "oauth_version": "1.0",
    }
    enc = lambda s: urllib.parse.quote(str(s), safe="~")
    pairs = sorted((enc(k), enc(v)) for k, v in {**params, **oauth}.items())
    base = "&".join([method.upper(), enc(url),
                     enc("&".join("%s=%s" % kv for kv in pairs))])
    key = "%s&%s" % (enc(consumer_secret), enc(token_secret))
    sig = base64.b64encode(hmac.new(key.encode(), base.encode(),
                                    hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join('%s="%s"' % (enc(k), enc(v))
                                for k, v in sorted(oauth.items()))


class BrickLinkReference(SupplierAdapter):
    key = "bricklink"
    name = "BrickLink (price reference)"
    capabilities = Capabilities(
        api="catalog", orders_via="portal", dropship=None, blind_ship=None,
        prints_booklet=False, moq_pieces=None, regions=("worldwide",),
        lead_time_days=None, part_numbering="bricklink", status="research",
        notes=("The API is for sellers. It covers the catalogue, the price "
               "guide and orders; with direction=out it can list purchases "
               "we made, but it has no call that creates an order or a cart. "
               "Used for reference prices only. Parts are genuine LEGO and "
               "arrive from several stores."),
    )

    def __init__(self, client=None):
        self.creds = tuple(os.environ.get(k, "") for k in (
            "BRICKLINK_CONSUMER_KEY", "BRICKLINK_CONSUMER_SECRET",
            "BRICKLINK_TOKEN", "BRICKLINK_TOKEN_SECRET"))
        self.api_currency = os.environ.get("BRICKLINK_CURRENCY", "USD")
        self.fx = float(os.environ.get("BRICKLINK_FX_TO_ILS", "3.7"))
        self._client = client

    @property
    def configured(self) -> bool:
        return all(self.creds)

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.configured:
            raise SupplierNotConfigured(self.key)
        import httpx
        params = params or {}
        url = API + path
        header = oauth1_header("GET", url, params, *self.creds)
        client = self._client or httpx
        resp = client.get(url, params=params,
                          headers={"Authorization": header}, timeout=20.0)
        resp.raise_for_status()
        body = resp.json()
        if body.get("meta", {}).get("code") not in (200, None):
            raise RuntimeError("BrickLink: %s" % body.get("meta"))
        return body.get("data", {})

    # ---- catalogue -------------------------------------------------------

    def get_products(self) -> list:
        # The catalogue is enormous; we only ever care about our library.
        # Prices are fetched per line by calculate_cost; listing them all
        # here would be one price-guide call per part and colour.
        back = {v: k for k, v in LDRAW_TO_BRICKLINK.items()}
        out = []
        for b in LIBRARY.all():
            for c in self._get("/items/PART/%s/colors" % b.part_id) or []:
                ours = back.get(c.get("color_id"))
                if ours is not None:
                    out.append(SupplierProduct(
                        self.key, "%s-%s" % (b.part_id, c["color_id"]),
                        b.part_id, ours, 0.0, "ILS", c.get("quantity")))
        return out

    def get_product_details(self, part_id: str, color_id: int):
        bl_color = bricklink_color(color_id)
        if bl_color is None:
            return None
        guide = self._get("/items/PART/%s/price" % part_id, {
            "color_id": bl_color, "guide_type": "stock", "new_or_used": "N",
            "currency_code": self.api_currency})
        avg = float(guide.get("avg_price") or 0.0)
        qty = int(guide.get("total_quantity") or 0)
        return SupplierProduct(self.key, "%s-%d" % (part_id, bl_color), part_id,
                               color_id, round(avg * self.fx, 4), "ILS", qty)

    def get_inventory(self, items: list) -> list:
        out = []
        for part, color in items:
            p = self.get_product_details(part, color)
            out.append(InventoryLevel(part, color, bool(p and p.available_qty),
                                      p.available_qty if p else 0))
        return out

    def calculate_cost(self, lines: list, weight_g: float,
                       ship_to: ShipTo | None = None) -> Quote:
        total, per_part, missing = 0.0, {}, []
        for l in lines:
            p = self.get_product_details(l.part_id, l.color_id)
            if not p or not p.unit_cost:
                missing.append({"part_id": l.part_id, "color_id": l.color_id,
                                "needed": l.quantity})
                continue
            per_part[l.part_id] = p.unit_cost
            total += p.unit_cost * l.quantity
        return Quote(self.name, "ILS", total, 0.0, 0.0, 14, missing, per_part)

    # ---- orders: not possible through this API ---------------------------

    def create_order(self, request):
        raise NotSupportedBySupplier(
            "BrickLink's API cannot place purchases; buy through the site.")

    def get_order_status(self, reference: str) -> str:
        raise NotSupportedBySupplier("BrickLink purchases are not tracked by API.")

    def get_tracking(self, reference: str):
        raise NotSupportedBySupplier("BrickLink purchases are not tracked by API.")

    def cancel_order(self, reference: str) -> bool:
        raise NotSupportedBySupplier("BrickLink purchases are not managed by API.")
