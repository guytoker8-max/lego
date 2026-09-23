"""The website's promises: what the customer approves is what is charged,
packed and sent to the supplier, and nothing is paid for twice.

Runs against the real app with test payments (no Stripe key) and the
built-in fulfilment route, so nothing leaves the machine.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import suppliers
from app.catalog import Catalog, internal_id
from app.commerce.payments import minor_units, verify_stripe_signature
from app.config import CATEGORY_STRATEGIES, PRESETS_BY_KEY, custom_preset
from app.main import app
from app.suppliers.ledger import purchase_order_bricklink_xml

ADMIN = {"X-Admin-Token": "test-admin"}
ADDRESS = {
    "email": "guy@example.com", "name": "Test Buyer", "phone": "050-0000000",
    "address": {"line1": "1 Herzl St", "city": "Tel Aviv",
                "postal_code": "6100000", "country": "IL"},
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _png(color=(200, 40, 40)) -> bytes:
    im = Image.new("RGB", (360, 360), "white")
    ImageDraw.Draw(im).ellipse((70, 60, 290, 320), fill=color)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# sizes and subjects
# ---------------------------------------------------------------------------

def test_custom_preset_grows_with_width():
    presets = [custom_preset(w) for w in (10, 20, 30, 40)]
    budgets = [p.max_pieces for p in presets]
    assert budgets == sorted(budgets) and len(set(budgets)) == 4
    assert all(150 <= b <= 7000 for b in budgets)
    # 20 cm is close to Medium's width, so close to Medium's budget.
    assert abs(presets[1].width_studs - PRESETS_BY_KEY["medium"].width_studs) <= 1


def test_custom_preset_clamps_silly_widths():
    assert custom_preset(1).width_studs == custom_preset(8).width_studs
    assert custom_preset(500).max_pieces <= 7000


def test_every_category_has_a_strategy():
    for key in ("pet", "person", "vehicle", "building", "object",
                "character", "other"):
        s = CATEGORY_STRATEGIES[key]
        assert s["label"]
        if key != "other":  # "other" leaves depth to the analysis
            assert 0 < s["depth_ratio"] <= 1.5


# ---------------------------------------------------------------------------
# catalogue
# ---------------------------------------------------------------------------

def test_catalog_parts_carry_the_spec_fields(client):
    parts = client.get("/api/catalog/parts").json()["parts"]
    assert parts
    p = parts[0]
    for field in ("part_id", "supplier_part_id", "type", "width", "length",
                  "height", "available_colors", "connection", "weight_g",
                  "cost", "retail_price", "supplier", "available", "sku",
                  "image", "shipping"):
        assert field in p, field
    svg = client.get("/api/catalog/parts/%s/image.svg" % p["part_id"])
    assert svg.status_code == 200 and svg.text.startswith("<svg")


def test_catalog_resolves_its_own_ids():
    cat = Catalog()
    for part in cat.parts()[:10]:
        assert cat.part(part.part_id).part_id == part.part_id
        assert internal_id(Catalog._resolve(part.part_id)) == part.part_id


# ---------------------------------------------------------------------------
# uploads and builds
# ---------------------------------------------------------------------------

def test_upload_rejects_things_that_are_not_images(client):
    r = client.post("/api/store/uploads",
                    files=[("files", ("x.png", b"not an image", "image/png"))])
    assert r.status_code in (400, 415)


def test_build_from_a_photo_reaches_a_priced_design(client):
    r = client.post("/api/store/uploads",
                    files=[("files", ("ball.png", _png(), "image/png"))])
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    r = client.post("/api/store/jobs/%s/build" % job_id,
                    json={"category": "object", "size": "mini"})
    assert r.status_code == 200, r.text

    seen, job = [], None
    deadline = time.time() + 180
    while time.time() < deadline:
        job = client.get("/api/store/jobs/%s" % job_id).json()
        active = [s["key"] for s in job["stages"] if s["state"] == "active"]
        seen.extend(a for a in active if not seen or seen[-1] != a)
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.3)
    assert job["status"] == "done", job.get("error")

    # Stages only move forward.
    order = [s["key"] for s in job["stages"]]
    idx = [order.index(k) for k in seen]
    assert idx == sorted(idx)

    design = client.get("/api/store/designs/%s" % job["model_id"]).json()
    assert sum(l["quantity"] for l in design["parts"]) > 0
    assert design["price"]["total"] > 0
    # Dimensions come from the model, not from the size that was asked for.
    assert design["dimensions_cm"]["width"] > 0


def test_unknown_category_is_refused(client):
    r = client.post("/api/store/uploads",
                    files=[("files", ("ball.png", _png(), "image/png"))])
    job_id = r.json()["id"]
    r = client.post("/api/store/jobs/%s/build" % job_id,
                    json={"category": "spaceship", "size": "mini"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# approval, checkout, payment, supplier
# ---------------------------------------------------------------------------

def test_checkout_requires_approval(client):
    r = client.post("/api/store/checkout",
                    json=dict(ADDRESS, model_id="example-object"))
    assert r.status_code in (409, 404)


def test_checkout_refuses_countries_we_do_not_ship_to(client):
    client.post("/api/store/designs/example-car/approve", json={})
    body = dict(ADDRESS, model_id="example-car",
                address=dict(ADDRESS["address"], country="US"))
    r = client.post("/api/store/checkout", json=body)
    assert r.status_code == 400


def test_approval_is_tied_to_the_exact_model(client):
    r = client.post("/api/store/designs/example-pet/approve",
                    json={"fingerprint": "0" * 64})
    assert r.status_code == 409


def test_paid_order_reaches_the_supplier_once(client):
    fp = client.post("/api/store/designs/example-pet/approve",
                     json={}).json()["fingerprint"]
    r = client.post("/api/store/checkout",
                    json=dict(ADDRESS, model_id="example-pet"))
    assert r.status_code == 200, r.text
    co = r.json()
    assert co["test_mode"] is True
    oid, token = co["order_id"], co["token"]

    # Nobody else can see it.
    assert client.get("/api/store/orders/%s?token=wrong" % oid).status_code == 404
    order = client.get("/api/store/orders/%s?token=%s" % (oid, token)).json()
    assert order["status"] == "awaiting_payment"
    assert "access_token" not in order and "lines" not in order

    paid = client.post("/api/store/orders/%s/test-pay?token=%s" % (oid, token)).json()
    assert paid["status"] != "awaiting_payment"
    again = client.post("/api/store/orders/%s/test-pay?token=%s" % (oid, token)).json()
    assert again["status"] == paid["status"]

    pos = [p for p in client.get("/api/admin/purchase-orders",
                                 headers=ADMIN).json()["purchase_orders"]
           if p.get("order_id") == oid]
    assert len(pos) == 1
    po = pos[0]
    assert po["fingerprint"] == fp
    assert po["blind_ship"] is True
    assert po["ship_to"]["country"] == "IL"

    design = client.get("/api/store/designs/example-pet").json()
    assert po["piece_count"] == sum(l["quantity"] for l in design["parts"])

    csv_text = client.get("/api/admin/purchase-orders/%s.csv" % po["reference"],
                          headers=ADMIN).text
    assert csv_text.splitlines()[0].startswith("supplier_sku,design_id")
    xml = client.get("/api/admin/purchase-orders/%s.xml" % po["reference"],
                     headers=ADMIN).text
    assert xml.startswith("<INVENTORY>") and xml.count("<ITEM>") == len(po["lines"])

    # The supplier moving it along shows up on the customer's order.
    r = client.post("/api/admin/purchase-orders/%s/status" % po["reference"],
                    headers=ADMIN,
                    json={"status": "shipped", "carrier": "Israel Post",
                          "tracking_number": "RR123456789IL"})
    assert r.status_code == 200
    order = client.get("/api/store/orders/%s?token=%s" % (oid, token)).json()
    assert order["status"] == "shipped"


def test_admin_routes_need_the_token(client):
    assert client.get("/api/admin/orders").status_code in (401, 403)
    assert client.get("/api/admin/orders",
                      headers={"X-Admin-Token": "nope"}).status_code in (401, 403)


def test_web_orders_stay_off_the_legacy_order_list(client):
    orders = client.get("/api/orders").json()
    listed = orders.get("orders", orders) if isinstance(orders, dict) else orders
    assert not any(o.get("access_token") for o in listed)


# ---------------------------------------------------------------------------
# suppliers
# ---------------------------------------------------------------------------

def test_researched_suppliers_are_listed_but_not_live(client):
    rows = {s["key"]: s for s in client.get("/api/admin/suppliers",
                                             headers=ADMIN).json()["suppliers"]}
    for key in ("wobrick", "brickwith", "marstoy"):
        assert rows[key]["capabilities"]["status"] == "not_contracted"
        assert rows[key]["capabilities"]["api"] == "none"
    assert rows["compatible"]["capabilities"]["status"] == "live"


def test_every_adapter_implements_the_contract():
    for a in suppliers.adapters():
        for method in ("get_products", "get_inventory", "get_product_details",
                       "calculate_cost", "create_order", "get_order_status",
                       "get_tracking", "cancel_order"):
            assert callable(getattr(a, method)), (a.key, method)


def test_price_list_supplier_quotes_from_its_csv(tmp_path):
    from app.suppliers import PriceListSupplier, PurchaseOrderLedger
    from app.suppliers.profiles import PROFILES
    prof = next(p for p in PROFILES if p["key"] == "wobrick")
    csv_path = tmp_path / "wobrick.csv"
    csv_path.write_text("design_id,color_id,supplier_sku,unit_cost,stock\n"
                        "3001,4,GDS-542-R,0.10,1000\n")
    s = PriceListSupplier(prof["key"], prof["name"],
                          PurchaseOrderLedger(str(tmp_path)),
                          capabilities=prof["capabilities"], currency="USD",
                          price_list_path=str(csv_path), fx_to_ils=3.5)

    class Line:
        part_id, color_id, quantity = "3001", 4, 10
        part_name, color_name = "Brick 2 x 4", "Red"

    q = s.calculate_cost([Line()], 23.0)
    assert not q.unavailable
    assert q.parts_cost == pytest.approx(3.5)  # 10 x $0.10 x 3.5


def test_bricklink_xml_maps_colours_and_flags_unknown_ones():
    xml = purchase_order_bricklink_xml({"lines": [
        {"part_id": "3001", "color_id": 4, "quantity": 12,
         "supplier_sku": "", "color_name": "Red"},
        {"part_id": "3024", "color_id": 9999, "quantity": 3,
         "supplier_sku": "", "color_name": "Moon"},
    ]})
    assert "<ITEMID>3001</ITEMID><COLOR>5</COLOR><MINQTY>12</MINQTY>" in xml
    assert "Moon (LDraw 9999)" in xml


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------

def _stripe_header(payload: bytes, secret: str, ts: int) -> str:
    sig = hmac.new(secret.encode(), b"%d." % ts + payload,
                   hashlib.sha256).hexdigest()
    return "t=%d,v1=%s" % (ts, sig)


def test_stripe_signature_accepts_only_fresh_genuine_events():
    payload = json.dumps({"type": "checkout.session.completed"}).encode()
    now = 1_800_000_000
    good = _stripe_header(payload, "whsec_x", now)
    assert verify_stripe_signature(payload, good, "whsec_x", now=now)
    assert not verify_stripe_signature(payload, good, "whsec_y", now=now)
    assert not verify_stripe_signature(payload + b" ", good, "whsec_x", now=now)
    assert not verify_stripe_signature(payload, good, "whsec_x", now=now + 3600)
    assert not verify_stripe_signature(payload, "garbage", "whsec_x", now=now)


def test_minor_units_round_money_correctly():
    assert minor_units(560.5) == 56050
    assert minor_units(0.1 + 0.2) == 30
