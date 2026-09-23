"""The web store's API: upload, build, approve, pay, track.

Everything here is a thin layer over the same engine the mobile app uses.
A design *is* a stored ``BrickModel``; its preview, parts list, price,
booklet and supplier order are all read from that one model, and the order
records the model's fingerprint so what ships is provably what was approved.

The flow, and the one rule each step enforces:

1. ``POST /uploads``          photos in.  Only real JPEG, PNG or WEBP images.
2. ``POST /jobs/{id}/build``  category + size.  Progress is the pipeline's own
                              stage reports -- no invented percentages.
3. ``GET  /designs/{id}``     the model, parts, price, checks.
4. ``POST /designs/{id}/approve``  the customer approves *this fingerprint*.
5. ``POST /checkout``         priced again server-side from the parts list;
                              refused if the model changed since approval.
6. payment on the provider's page; confirmed by webhook or on return.
7. only then is the supplier order created.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from .catalog import Catalog, internal_id, part_svg
from .commerce.booklet import booklet_pdf
from .commerce.payments import PaymentError, TestPayment, minor_units, provider_from_env
from .config import (CATEGORY_STRATEGIES, CUSTOM_WIDTHS_CM, DETAIL_MODIFIERS,
                     PRESETS_BY_KEY, SETTINGS, custom_preset)
from .library import LIBRARY, color_by_id
from .models import BrickModel

log = logging.getLogger(__name__)

router = APIRouter()

# Bound at start-up by main.py, which owns the engine.
_CORE: dict = {}
PAYMENTS = provider_from_env()
CATALOG = Catalog(SETTINGS.supplier)


def bind(store, pipeline, orders) -> None:
    _CORE.update(store=store, pipeline=pipeline, orders=orders)


def _store():
    return _CORE["store"]


def _pipeline():
    return _CORE["pipeline"]


def _orders():
    return _CORE["orders"]


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
SHIP_COUNTRIES = tuple(c.strip().upper() for c in os.environ.get(
    "BRICKSNAP_SHIP_COUNTRIES", "IL").split(",") if c.strip())
# The shipping keys checkout accepts, named once so the client can ask
# rather than hard-coding the same two strings.
CHECKOUT_SHIPPING = ("standard", "express")
PUBLIC_URL = os.environ.get("BRICKSNAP_PUBLIC_URL", "").rstrip("/")
ADMIN_TOKEN = os.environ.get("BRICKSNAP_ADMIN_TOKEN", "")
MAX_CONCURRENT_BUILDS = int(os.environ.get("BRICKSNAP_MAX_BUILDS", "2"))
BUILDS_PER_HOUR = int(os.environ.get("BRICKSNAP_BUILDS_PER_HOUR", "20"))

# What the customer picks, and what the engine is asked for.
SIZE_OPTIONS = {
    "mini":     {"label": "Mini", "answers": {"size": "mini", "detail": "simple"},
                 "blurb": ["Small model", "Low piece count", "Lower price"]},
    "standard": {"label": "Standard", "answers": {"size": "medium", "detail": "balanced"},
                 "blurb": ["Balanced detail and price"]},
    "detailed": {"label": "Detailed", "answers": {"size": "large", "detail": "detailed"},
                 "blurb": ["More pieces", "Higher detail", "Higher price"]},
    "custom":   {"label": "Custom", "answers": {"size": "custom", "detail": "balanced"},
                 "blurb": ["Choose the approximate width"]},
}

# The progress screen's stages, in order.  Keys are what the pipeline
# reports; the labels are the customer's words for them.
STAGES = (
    ("queued", "Waiting for a free builder..."),
    ("analyzing", "Analyzing your photo..."),
    ("shape", "Understanding the shape..."),
    ("structure", "Building the structure..."),
    ("details", "Mapping the details..."),
    ("bricks", "Selecting compatible bricks..."),
    ("supports", "Adding structural supports..."),
    ("validating", "Checking stability..."),
    ("instructions", "Writing the instructions..."),
    ("pricing", "Pricing your set..."),
)
STAGE_INDEX = {k: i for i, (k, _) in enumerate(STAGES)}

_BUILD_SLOTS = threading.Semaphore(MAX_CONCURRENT_BUILDS)
_RECENT_BUILDS: dict = defaultdict(deque)
_RATE_LOCK = threading.Lock()


def _budget_for(option: str, width_cm: float | None = None) -> dict:
    """The piece cap and size limit a choice really sets, before building."""
    ans = SIZE_OPTIONS[option]["answers"]
    preset = (custom_preset(width_cm or 20) if option == "custom"
              else PRESETS_BY_KEY[ans["size"]])
    pieces = int(preset.max_pieces * DETAIL_MODIFIERS[ans["detail"]]["pieces"])
    return {"max_pieces": pieces,
            "max_width_cm": round(preset.width_studs * 0.8, 1),
            "colors": preset.colors}


@router.get("/api/store/config")
def store_config():
    b = SETTINGS.branding
    return {
        "brand": b.product_name,
        "disclaimer": b.disclaimer,
        "short_disclaimer": b.short_disclaimer,
        "currency": "ILS", "symbol": "₪",
        "categories": [{"key": k, "label": v["label"]}
                       for k, v in CATEGORY_STRATEGIES.items()],
        "sizes": [dict(key=k, label=v["label"], blurb=v["blurb"],
                       **({} if k == "custom" else _budget_for(k)))
                  for k, v in SIZE_OPTIONS.items()],
        "custom_widths_cm": [dict(width_cm=w, **_budget_for("custom", w))
                             for w in CUSTOM_WIDTHS_CM],
        "max_photos": SETTINGS.max_references,
        "max_upload_mb": SETTINGS.max_upload_mb,
        "formats": ["image/jpeg", "image/png", "image/webp"],
        "ship_countries": list(SHIP_COUNTRIES),
        # Which of the pricing engine's options checkout will take.
        # The engine also quotes collection, which has no checkout.
        "shipping_methods": list(CHECKOUT_SHIPPING),
        "payments": PAYMENTS.public(),
        "vision": bool(SETTINGS.anthropic_api_key),
    }


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------

def _check_image(data: bytes, name: str) -> str:
    """Open it as an image, or refuse it.  Returns the file extension.

    The extension and the browser's content type are only claims; Pillow
    reading the bytes is the check.  A renamed PDF is refused here instead
    of failing somewhere in the pipeline.
    """
    import io
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise HTTPException(
            415, "%s isn't a photo we can read. Please use JPG, PNG or WEBP."
                 % (name or "That file")) from None
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(
            415, "%s is a %s. Please use JPG, PNG or WEBP." % (name or "That file", fmt))
    return ALLOWED_FORMATS[fmt]


@router.post("/api/store/uploads")
async def upload_photos(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "Add at least one photo.")
    if len(files) > SETTINGS.max_references:
        raise HTTPException(400, "Up to %d photos, please." % SETTINGS.max_references)
    store = _store()
    job_id = store.new_job()
    folder = store.upload_dir(job_id)
    limit = SETTINGS.max_upload_mb * 1024 * 1024
    photos, paths = [], []
    for i, f in enumerate(files):
        data = await f.read()
        if not data:
            raise HTTPException(400, "%s is empty." % (f.filename or "A photo"))
        if len(data) > limit:
            raise HTTPException(413, "%s is larger than %d MB." % (
                f.filename or "A photo", SETTINGS.max_upload_mb))
        ext = _check_image(data, f.filename or "")
        path = os.path.join(folder, "ref%d%s" % (i, ext))
        with open(path, "wb") as fh:
            fh.write(data)
        paths.append(path)
        photos.append({"url": "/api/store/jobs/%s/photos/%d" % (job_id, i),
                       "name": f.filename or "photo %d" % (i + 1)})
    job = {"id": job_id, "kind": "web", "status": "uploaded",
           "photos": photos, "paths": paths, "created_at": time.time()}
    store.save_job(job)
    return _public_job(job)


@router.get("/api/store/jobs/{job_id}/photos/{n}")
def job_photo(job_id: str, n: int):
    job = _job(job_id)
    paths = job.get("paths") or []
    if n < 0 or n >= len(paths) or not os.path.exists(paths[n]):
        raise HTTPException(404, "No such photo.")
    return FileResponse(paths[n])


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _rate_limit(ip: str) -> None:
    now = time.time()
    with _RATE_LOCK:
        q = _RECENT_BUILDS[ip]
        while q and q[0] < now - 3600:
            q.popleft()
        if len(q) >= BUILDS_PER_HOUR:
            raise HTTPException(
                429, "That's a lot of sets in one hour. Please try again a "
                     "little later.")
        q.append(now)


@router.post("/api/store/jobs/{job_id}/build")
def build(job_id: str, body: dict, request: Request):
    job = _job(job_id)
    if job.get("status") == "building":
        return _public_job(job)
    category = (body or {}).get("category") or "other"
    if category not in CATEGORY_STRATEGIES:
        raise HTTPException(400, "Pick what the photo shows.")
    size = (body or {}).get("size") or "standard"
    if size not in SIZE_OPTIONS:
        raise HTTPException(400, "Pick a size.")
    answers = dict(SIZE_OPTIONS[size]["answers"], priority="balanced",
                   unseen_back="yes", category=category)
    if size == "custom":
        try:
            answers["width_cm"] = float((body or {}).get("width_cm"))
        except (TypeError, ValueError):
            raise HTTPException(400, "Choose a width for a custom size.") from None
    angles = (body or {}).get("angles") or None
    _rate_limit(request.client.host if request.client else "?")

    job.update(status="building", category=category, size=size,
               answers=answers, stages=_stages("queued"), current="queued",
               message=STAGES[0][1], error=None, model_id=None,
               retries=0, started_at=time.time())
    _store().save_job(job)
    threading.Thread(target=_run_build, args=(job_id, angles),
                     daemon=True).start()
    return _public_job(job)


def _stages(current: str, done_all: bool = False) -> list:
    at = STAGE_INDEX.get(current, 0)
    return [{"key": k, "label": label,
             "state": "done" if done_all or i < at else
                      "active" if i == at else "pending"}
            for i, (k, label) in enumerate(STAGES)]


def _run_build(job_id: str, angles) -> None:
    store, pipeline = _store(), _pipeline()
    job = store.get_job(job_id)
    lock = threading.Lock()

    def emit(stage, message, progress=None):
        # Stages only move forward.  A second pass at a smaller width reports
        # its stages again; those are shown as a retry note, not as progress
        # running backwards.
        if stage not in STAGE_INDEX:
            return
        with lock:
            cur = STAGE_INDEX.get(job.get("current"), 0)
            new = STAGE_INDEX[stage]
            if new >= cur:
                job["current"] = stage
                job["stages"] = _stages(stage)
                job["message"] = dict(STAGES)[stage]
            elif "again" in (message or ""):
                job["retries"] = job.get("retries", 0) + 1
                job["message"] = ("Resizing to fit the piece count "
                                  "(pass %d)..." % (job["retries"] + 1))
            store.save_job(job)

    with _BUILD_SLOTS:
        try:
            emit("analyzing", "")
            analysis, views = pipeline.analyze(job["paths"], angles,
                                               job.get("category"))
            result = pipeline.build(views, analysis, job["answers"], emit)
            emit("pricing", "")
            model = BrickModel.from_dict(result["model"])
            model_id = job_id
            try:
                from .pipeline.preview import thumbnail
                thumbnail(model).save(store.preview_path(model_id))
            except Exception:
                log.warning("no preview for %s", model_id)
            store.save_model(model_id, {
                "model": result["model"], "summary": result["summary"],
                "status": "draft", "references": job["paths"],
                "thumbnail": "/api/models/%s/preview" % model_id,
                "web": {"category": job.get("category"), "size": job.get("size"),
                        "width_cm": job["answers"].get("width_cm"),
                        "photos": job.get("photos", []), "job_id": job_id},
            })
            job.update(status="done", current="done", stages=_stages("pricing", True),
                       message="Your set is ready.", model_id=model_id,
                       warnings=result.get("warnings", []))
        except Exception as exc:
            from .pipeline.geometry import EmptySilhouetteError
            from .pipeline.reference_analyzer import NoUsableReferenceError
            from .pipeline.runner import InconsistentModelError, UnbuildableError
            known = (EmptySilhouetteError, NoUsableReferenceError,
                     UnbuildableError, InconsistentModelError)
            if not isinstance(exc, known):
                log.exception("web build failed")
            job.update(status="failed",
                       error=str(exc) if isinstance(exc, known) else
                       "Something went wrong building this model. Please try "
                       "again, or try a different photo.")
        store.save_job(job)


@router.get("/api/store/jobs/{job_id}")
def get_job(job_id: str):
    return _public_job(_job(job_id))


def _job(job_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id or ""):
        raise HTTPException(404, "No such job.")
    try:
        job = _store().get_job(job_id)
    except Exception:
        raise HTTPException(404, "No such job.") from None
    if job.get("kind") != "web":
        raise HTTPException(404, "No such job.")
    return job


def _public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in ("paths", "answers")}


# ---------------------------------------------------------------------------
# designs
# ---------------------------------------------------------------------------

def _record(model_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-z\-]{6,64}", model_id or ""):
        raise HTTPException(404, "No such design.")
    try:
        return _store().get_model(model_id)
    except Exception:
        raise HTTPException(404, "No such design.") from None


@router.get("/api/store/designs/{model_id}")
def get_design(model_id: str):
    rec = _record(model_id)
    model = BrickModel.from_dict(rec["model"])
    p = _pipeline()
    lines = p.inventory.bill_of_materials(model)
    price = p.pricing.price(lines, model.weight_g)
    fp = model.fingerprint()
    approval = rec.get("approval") or {}
    summary = p.package(model, lines)["summary"]
    val = model.validation or {}
    return {
        "id": model_id,
        "name": model.name,
        "fingerprint": fp,
        "summary": summary,
        "dimensions_cm": {"width": model.dimensions_cm[0],
                          "height": model.dimensions_cm[1],
                          "depth": model.dimensions_cm[2]},
        "layers": len({b.y for b in model.bricks}),
        "parts": [_part_line(l) for l in lines],
        "distinct_parts": len({l.part_id for l in lines}),
        "price": _public_price(price),
        "checks": {
            "ok": bool(val.get("ok", True)),
            "repairs": val.get("repairs", []),
            "warnings": [i.get("message") for i in val.get("issues", [])
                         if i.get("severity") == "warning"],
            "stats": val.get("stats", {}),
        },
        "approval": {
            "approved": approval.get("fingerprint") == fp,
            "stale": bool(approval) and approval.get("fingerprint") != fp,
            "at": approval.get("at"),
        },
        "web": {k: v for k, v in (rec.get("web") or {}).items() if k != "job_id"},
        "can_resize": bool(rec.get("references")) and
                      all(os.path.exists(x) for x in rec.get("references", [])),
        "example": bool(rec.get("example")),
        "thumbnail": "/api/models/%s/preview" % model_id,
        "booklet": "/api/store/designs/%s/booklet.pdf" % model_id,
    }


def _part_line(l) -> dict:
    b = LIBRARY.get(l.part_id)
    return {"part_id": internal_id(b), "design_id": l.part_id,
            "name": l.part_name, "type": b.kind,
            "color_id": l.color_id, "color_name": l.color_name,
            "color_hex": l.color_hex, "quantity": l.quantity,
            "image": "/api/catalog/parts/%s/image.svg?color=%d"
                     % (l.part_id, l.color_id)}


def _public_price(price: dict) -> dict:
    """The customer sees the set price, VAT and shipping; not our costs."""
    br = price["breakdown"]
    return {"currency": price["currency"], "symbol": price["symbol"],
            "set_price": price["set_price"], "vat": br["vat"],
            "shipping": br["shipping"], "total": price["total"],
            "shipping_options": [o for o in price["shipping_options"]
                                 if o["key"] != "pickup"],
            "shipping_selected": price["shipping_selected"],
            "production_days": price["production_days"]}


@router.post("/api/store/designs/{model_id}/resize")
def resize(model_id: str, body: dict, request: Request):
    """A different size is a new build from the same photos, not a scale."""
    rec = _record(model_id)
    refs = rec.get("references") or []
    if not refs or not all(os.path.exists(x) for x in refs):
        raise HTTPException(409, "The original photos aren't available for "
                                 "this design, so it can't be resized.")
    store = _store()
    job_id = store.new_job()
    web = rec.get("web") or {}
    job = {"id": job_id, "kind": "web", "status": "uploaded",
           "photos": web.get("photos", []), "paths": refs,
           "created_at": time.time(), "parent": model_id}
    store.save_job(job)
    body = dict(body or {})
    body.setdefault("category", web.get("category") or "other")
    return build(job_id, body, request)


@router.post("/api/store/designs/{model_id}/approve")
def approve(model_id: str, body: dict | None = None):
    rec = _record(model_id)
    model = BrickModel.from_dict(rec["model"])
    fp = model.fingerprint()
    expected = (body or {}).get("fingerprint")
    if expected and expected != fp:
        raise HTTPException(409, "This design changed since you looked at it. "
                                 "Please review it again.")
    p = _pipeline()
    lines = p.inventory.bill_of_materials(model)
    if p.inventory.reconcile(model, lines):
        raise HTTPException(409, "This design's parts list doesn't match its "
                                 "model, so it can't be approved.")
    price = p.pricing.price(lines, model.weight_g)
    rec["approval"] = {"fingerprint": fp, "at": time.time(),
                       "piece_count": model.piece_count,
                       "set_price": price["set_price"]}
    rec["status"] = "approved"
    _store().save_model(model_id, rec)
    return {"approved": True, "fingerprint": fp}


@router.get("/api/store/designs/{model_id}/booklet.pdf")
def booklet(model_id: str):
    rec = _record(model_id)
    model = BrickModel.from_dict(rec["model"])
    path = os.path.join(_store().root, "booklets", "%s.pdf" % model.fingerprint())
    if not os.path.exists(path):
        p = _pipeline()
        if not model.steps:
            p.instructions.generate(model)
        booklet_pdf(model, p.instructions.describe(model),
                    p.inventory.summary(model), path,
                    brand=SETTINGS.branding.product_name,
                    disclaimer=SETTINGS.branding.short_disclaimer)
    return FileResponse(path, media_type="application/pdf",
                        filename="%s-instructions.pdf"
                                 % re.sub(r"[^A-Za-z0-9]+", "-", model.name).strip("-"))


# ---------------------------------------------------------------------------
# catalogue
# ---------------------------------------------------------------------------

@router.get("/api/catalog/parts")
def catalog_parts():
    return {"parts": [p.to_dict() for p in CATALOG.parts()]}


@router.get("/api/catalog/parts/{part_id}")
def catalog_part(part_id: str, color: int | None = None):
    try:
        return CATALOG.part(part_id, color).to_dict()
    except KeyError:
        raise HTTPException(404, "No such part.") from None


@router.get("/api/catalog/parts/{part_id}/image.svg")
def catalog_image(part_id: str, color: int = 71):
    try:
        b = Catalog._resolve(part_id)
        hex_color = color_by_id(color).hex
    except KeyError:
        raise HTTPException(404, "No such part or colour.") from None
    return Response(part_svg(b, hex_color), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------------------
# checkout
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _base_url(request: Request) -> str:
    if PUBLIC_URL:
        return PUBLIC_URL
    origin = request.headers.get("origin")
    return (origin or str(request.base_url)).rstrip("/")


@router.post("/api/store/checkout")
def checkout(body: dict, request: Request):
    body = body or {}
    model_id = body.get("model_id") or ""
    rec = _record(model_id)
    model = BrickModel.from_dict(rec["model"])
    fp = model.fingerprint()

    approval = rec.get("approval") or {}
    if approval.get("fingerprint") != fp:
        raise HTTPException(409, "Please approve the design before ordering.")

    email = (body.get("email") or "").strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address.")
    addr = body.get("address") or {}
    ship_to = {
        "name": (body.get("name") or "").strip(),
        "line1": (addr.get("line1") or "").strip(),
        "line2": (addr.get("line2") or "").strip(),
        "city": (addr.get("city") or "").strip(),
        "region": (addr.get("region") or "").strip(),
        "postal_code": (addr.get("postal_code") or "").strip(),
        "country": (addr.get("country") or "").strip().upper(),
        "phone": (body.get("phone") or "").strip(),
        "email": email,
    }
    missing = [k for k in ("name", "line1", "city", "postal_code", "country")
               if not ship_to[k]]
    if missing:
        raise HTTPException(400, "Please fill in your %s."
                            % ", ".join(m.replace("line1", "street address")
                                        .replace("postal_code", "postcode")
                                        for m in missing))
    if ship_to["country"] not in SHIP_COUNTRIES:
        raise HTTPException(400, "We can't ship to that country yet.")
    shipping = body.get("shipping") or "standard"
    if shipping not in CHECKOUT_SHIPPING:
        raise HTTPException(400, "Pick a shipping option.")

    p = _pipeline()
    lines = p.inventory.bill_of_materials(model)
    if p.inventory.reconcile(model, lines):
        raise HTTPException(409, "This design can't be ordered right now.")
    short = p.inventory.check_availability(lines)
    if short:
        raise HTTPException(409, "Some parts are out of stock: %s" % ", ".join(
            "%s %s" % (s["color_name"], s["part_name"]) for s in short[:3]))
    # Priced again here, from the parts list.  Whatever the page showed, this
    # is the number that is charged.
    price = p.pricing.price(lines, model.weight_g, shipping)
    if price.get("unavailable"):
        raise HTTPException(409, "Our supplier can't fill this parts list yet.")

    orders = _orders()
    order = orders.create_pending(
        model_id=model_id, fingerprint=fp, price=price,
        piece_count=model.piece_count, lines=lines, email=email,
        ship_to=ship_to, shipping_method=shipping, approval=approval,
        supplier_key=orders.supplier_key or SETTINGS.supplier)

    base = _base_url(request)
    try:
        session = PAYMENTS.create(
            order, product_name="%s brick set" % model.name,
            success_url="%s/order/%s?token=%s&session_id={CHECKOUT_SESSION_ID}"
                        % (base, order.id, order.access_token),
            cancel_url="%s/design/%s?checkout=cancelled" % (base, model_id))
    except PaymentError as exc:
        orders.cancel(order.id, "payment session failed: %s" % exc)
        raise HTTPException(502, "Payment is unavailable right now. Nothing "
                                 "was charged. Please try again.") from None
    order.payment = {"provider": session["provider"],
                     "reference": session["reference"],
                     "test_mode": session.get("test_mode", False)}
    _store().save_order(order)
    return {"order_id": order.id, "token": order.access_token,
            "redirect_url": session["redirect_url"],
            "test_mode": session.get("test_mode", False),
            "total": price["total"]}


def _order_for(order_id: str, token: str):
    if not re.fullmatch(r"[0-9a-f]{32}", order_id or ""):
        raise HTTPException(404, "No such order.")
    try:
        order = _store().get_order(order_id)
    except Exception:
        raise HTTPException(404, "No such order.") from None
    import hmac
    if not order.access_token or not hmac.compare_digest(
            order.access_token, token or ""):
        raise HTTPException(404, "No such order.")
    return order


def _booklet_url(order) -> str:
    base = PUBLIC_URL or ""
    return "%s/api/store/designs/%s/booklet.pdf" % (base, order.model_id)


def _confirm(order, paid: dict | None):
    """Mark an order paid if the provider's figures match the order's."""
    if not paid or order.status != "awaiting_payment":
        return order
    if paid.get("order_id") and paid["order_id"] != order.id:
        log.error("payment %s names another order", paid.get("reference"))
        return order
    if paid.get("amount_minor") is not None and \
            int(paid["amount_minor"]) != minor_units(order.price["total"]):
        log.error("amount mismatch on %s: paid %s, expected %s", order.id,
                  paid["amount_minor"], minor_units(order.price["total"]))
        return order
    return _orders().mark_paid(order.id, paid, booklet_url=_booklet_url(order))


@router.get("/api/store/orders/{order_id}")
def get_order(order_id: str, token: str = "", session_id: str = ""):
    order = _order_for(order_id, token)
    if order.status == "awaiting_payment" and \
            not isinstance(PAYMENTS, TestPayment):
        ref = session_id or order.payment.get("reference")
        if ref:
            try:
                order = _confirm(order, PAYMENTS.verify(ref))
            except PaymentError as exc:
                log.warning("could not verify payment for %s: %s", order.id, exc)
    rec = {}
    try:
        rec = _store().get_model(order.model_id)
    except Exception:
        pass
    out = order.public()
    out["design"] = {"id": order.model_id,
                     "name": rec.get("model", {}).get("name", "Your set"),
                     "thumbnail": "/api/models/%s/preview" % order.model_id}
    out["payments"] = PAYMENTS.public()
    return out


@router.post("/api/store/orders/{order_id}/test-pay")
def test_pay(order_id: str, token: str = ""):
    """The test-mode "pay" button.  Refused whenever a real provider is set."""
    if not isinstance(PAYMENTS, TestPayment):
        raise HTTPException(404, "Not available.")
    order = _order_for(order_id, token)
    order = _confirm(order, {"order_id": order.id,
                             "amount_minor": minor_units(order.price["total"]),
                             "currency": order.price.get("currency"),
                             "reference": "test_%s" % order.id[:12],
                             "provider": "test", "test_mode": True})
    return order.public()


@router.post("/api/store/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        paid = PAYMENTS.parse_webhook(payload, {k.lower(): v for k, v in
                                                request.headers.items()})
    except PaymentError as exc:
        raise HTTPException(400, str(exc)) from None
    if paid and paid.get("order_id"):
        try:
            order = _store().get_order(paid["order_id"])
        except Exception:
            return {"received": True, "unknown_order": True}
        _confirm(order, paid)
    return {"received": True}


# ---------------------------------------------------------------------------
# examples
# ---------------------------------------------------------------------------

@router.get("/api/store/examples")
def examples():
    from .examples import list_examples
    out = list_examples()
    p = _pipeline()
    for ex in out:
        try:
            model = BrickModel.from_dict(_store().get_model(ex["model_id"])["model"])
            lines = p.inventory.bill_of_materials(model)
            ex["price"] = p.pricing.price(lines, model.weight_g)["set_price"]
        except Exception:
            ex["price"] = None
    return {"examples": out}


@router.get("/api/store/examples/{slug}/source.png")
def example_source(slug: str):
    from .examples import source_response
    return source_response(slug)


# ---------------------------------------------------------------------------
# operations
# ---------------------------------------------------------------------------

def _admin(token: str | None) -> None:
    import hmac
    if not ADMIN_TOKEN:
        raise HTTPException(403, "Set BRICKSNAP_ADMIN_TOKEN to use operations.")
    if not hmac.compare_digest(ADMIN_TOKEN, token or ""):
        raise HTTPException(401, "Wrong operations token.")


@router.get("/api/admin/orders")
def admin_orders(x_admin_token: str = Header("")):
    _admin(x_admin_token)
    return {"orders": [o for o in _store().list_orders() if o.get("access_token")]}


@router.post("/api/admin/orders/{order_id}/sync")
def admin_sync(order_id: str, x_admin_token: str = Header("")):
    _admin(x_admin_token)
    return _orders().sync_from_supplier(order_id).to_dict()


@router.post("/api/admin/orders/{order_id}/cancel")
def admin_cancel(order_id: str, body: dict | None = None,
                 x_admin_token: str = Header("")):
    _admin(x_admin_token)
    orders = _orders()
    order = _store().get_order(order_id)
    refund = None
    if order.payment.get("status") == "paid":
        try:
            refund = PAYMENTS.refund(order.payment)
        except PaymentError as exc:
            raise HTTPException(502, "Refund failed: %s" % exc) from None
    try:
        order = orders.cancel(order_id, (body or {}).get("reason", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if refund:
        order.payment = dict(order.payment, refund=refund)
        _store().save_order(order)
    return order.to_dict()


@router.get("/api/admin/suppliers")
def admin_suppliers(x_admin_token: str = Header("")):
    _admin(x_admin_token)
    from .suppliers import adapters
    out = []
    for a in adapters():
        d = a.describe()
        d["configured"] = bool(getattr(a, "configured", True))
        d["active"] = a.key == (_orders().supplier_key or SETTINGS.supplier)
        out.append(d)
    return {"suppliers": out}


@router.get("/api/admin/purchase-orders")
def admin_pos(x_admin_token: str = Header("")):
    _admin(x_admin_token)
    from . import suppliers
    return {"purchase_orders": suppliers.LEDGER.list()}


@router.get("/api/admin/purchase-orders/{reference}.csv")
def admin_po_csv(reference: str, x_admin_token: str = Header("")):
    _admin(x_admin_token)
    from . import suppliers
    po = suppliers.LEDGER.get(reference)
    if not po:
        raise HTTPException(404, "No such purchase order.")
    return PlainTextResponse(suppliers.purchase_order_csv(po),
                             media_type="text/csv")


@router.get("/api/admin/purchase-orders/{reference}.xml")
def admin_po_xml(reference: str, x_admin_token: str = Header("")):
    _admin(x_admin_token)
    from . import suppliers
    po = suppliers.LEDGER.get(reference)
    if not po:
        raise HTTPException(404, "No such purchase order.")
    return PlainTextResponse(suppliers.purchase_order_bricklink_xml(po),
                             media_type="application/xml")


@router.post("/api/admin/purchase-orders/{reference}/status")
def admin_po_status(reference: str, body: dict, x_admin_token: str = Header("")):
    _admin(x_admin_token)
    from . import suppliers
    tracking = None
    if (body or {}).get("tracking_number"):
        tracking = {"carrier": body.get("carrier", ""),
                    "number": body["tracking_number"],
                    "url": body.get("tracking_url", "")}
    try:
        po = suppliers.LEDGER.advance(reference, (body or {}).get("status", ""),
                                      tracking=tracking,
                                      note=(body or {}).get("note", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except KeyError:
        raise HTTPException(404, "No such purchase order.") from None
    if po.get("order_id"):
        _orders().sync_from_supplier(po["order_id"])
    return po


# ---------------------------------------------------------------------------
# the website itself
# ---------------------------------------------------------------------------

def mount_web(app) -> None:
    """Serve the built website from the same process, if it has been built.

    Any path that is not an API route gets index.html, so a deep link like
    /design/abc123 opens the right page instead of a 404.
    """
    dist = os.environ.get("BRICKSNAP_WEB_DIST") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "web", "dist")
    if not os.path.isdir(dist):
        log.info("no built website at %s; API only", dist)
        return
    index = os.path.join(dist, "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        full = os.path.normpath(os.path.join(dist, path))
        if path and full.startswith(dist) and os.path.isfile(full):
            cache = ("public, max-age=31536000, immutable"
                     if "/assets/" in full else "public, max-age=300")
            return FileResponse(full, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
