"""The HTTP API.

Thin on purpose: every route validates its input, calls one pipeline stage or
service, and returns.  No modelling happens here.

Two things are deliberate.  The Anthropic key is read from the server's
environment and never sent to a client, and no payment detail is accepted by
any route -- the purchase route hands back a provider handoff instead.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import SETTINGS, PRESETS_BY_KEY
from .library import LIBRARY, color_by_id
from .library.suppliers import REGISTRY
from .models import BrickModel
from .pipeline.editor import ModelEditor
from .pipeline.geometry import EmptySilhouetteError
from .pipeline.orders import OrderService, STATUSES
from .pipeline.preview import thumbnail
from .pipeline.reference_analyzer import NoUsableReferenceError
from .pipeline.runner import (BuildPipeline, InconsistentModelError,
                              UnbuildableError)
from .storage import NotFound, Store

log = logging.getLogger(__name__)

app = FastAPI(title="BrickSnap API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)

STORE = Store(SETTINGS.data_dir)
# Supplier adapters first: the pricing engine inside the pipeline picks its
# supplier from the registry when it is built.
from . import suppliers as _suppliers  # noqa: E402
_suppliers.configure(SETTINGS.data_dir)
PIPELINE = BuildPipeline(api_key=SETTINGS.anthropic_api_key or None)
ORDERS = OrderService(STORE, supplier_key=SETTINGS.supplier)
EDITOR = ModelEditor(api_key=SETTINGS.anthropic_api_key or None)

# Analysis results held between the upload call and the build call.  Small,
# short-lived, and re-derivable from the uploads if the process restarts.
_SESSIONS: dict = {}
_SESSION_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    return SETTINGS.public()


@app.get("/api/library/bricks")
def get_bricks():
    """The parts catalogue, so the client can render any model it is given."""
    return {"parts": [
        {"part_id": b.part_id, "name": b.name, "w": b.w, "d": b.d, "h": b.h,
         "kind": b.kind, "weight_g": b.weight_g, "has_studs": b.has_studs}
        for b in LIBRARY.all()
    ], "suppliers": [{"key": k, "name": s.name} for k, s in REGISTRY.items()]}


# ---------------------------------------------------------------------------
# upload + analysis
# ---------------------------------------------------------------------------

CLIENT_HEADER = "x-bricksnap-client"


def _client(request: Request) -> str:
    """Which install is asking.

    Not an identity: the app makes this up once and keeps it. It exists so a
    set belongs to the phone that built it. Without it a shared server shows
    every visitor everyone else's sets, which is both wrong and a leak.
    """
    return (request.headers.get(CLIENT_HEADER) or "").strip()[:64]


@app.post("/api/jobs")
async def create_job(request: Request,
                     files: list[UploadFile] = File(...),
                     angles: str = Form("")):
    """Take the photos, analyse them, and say what still needs deciding."""
    if not files:
        raise HTTPException(400, "Upload at least one photo.")
    if len(files) > SETTINGS.max_references:
        raise HTTPException(
            400, "Up to %d photos, please." % SETTINGS.max_references)

    job_id = STORE.new_job()
    folder = STORE.upload_dir(job_id)
    paths = []
    limit = SETTINGS.max_upload_mb * 1024 * 1024
    for i, f in enumerate(files):
        data = await f.read()
        if len(data) > limit:
            raise HTTPException(
                413, "%s is larger than %d MB." % (f.filename or "That photo",
                                                   SETTINGS.max_upload_mb))
        if not data:
            raise HTTPException(400, "One of the photos was empty.")
        path = os.path.join(folder, "ref%d%s" % (i, _ext(f.filename)))
        with open(path, "wb") as fh:
            fh.write(data)
        paths.append(path)

    angle_list = [a.strip() for a in angles.split(",") if a.strip()] or None
    try:
        analysis, views = PIPELINE.analyze(paths, angle_list)
    except NoUsableReferenceError as exc:
        raise HTTPException(400, str(exc)) from None
    except Exception as exc:
        log.exception("analysis failed")
        raise HTTPException(
            500, "The photo could not be analysed. Please try another.") from None

    with _SESSION_LOCK:
        _SESSIONS[job_id] = {"analysis": analysis, "views": views,
                             "paths": paths, "at": time.time(),
                             "owner": _client(request)}
        _sweep_sessions()

    job = {"id": job_id, "status": "awaiting_answers",
           "analysis": analysis.to_dict(), "questions": analysis.questions,
           "reference_count": len(views)}
    STORE.save_job(job)
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return STORE.get_job(job_id)
    except NotFound:
        raise HTTPException(404, "No such job.") from None


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/build")
def start_build(request: Request, job_id: str, answers: dict = None):
    """Kick the build off in the background and report progress as it runs."""
    answers = answers or {}
    with _SESSION_LOCK:
        session = _SESSIONS.get(job_id)
    if session is None:
        raise HTTPException(
            410, "That upload has expired. Please upload the photo again.")

    job = {"id": job_id, "status": "building", "stage": "analyzing",
           "message": "Analysing your model...", "progress": 0.1,
           "answers": answers}
    STORE.save_job(job)

    def run():
        def emit(stage, message, progress):
            STORE.save_job({"id": job_id, "status": "building", "stage": stage,
                            "message": message, "progress": progress,
                            "answers": answers})
        try:
            result = PIPELINE.build(session["views"], session["analysis"],
                                    answers, emit)
        except (EmptySilhouetteError, UnbuildableError,
                InconsistentModelError) as exc:
            STORE.save_job({"id": job_id, "status": "failed",
                            "error": str(exc), "recoverable": True,
                            "progress": 1.0})
            return
        except Exception as exc:
            log.exception("build failed")
            STORE.save_job({"id": job_id, "status": "failed",
                            "error": "Something went wrong building this model.",
                            "recoverable": True, "progress": 1.0})
            return

        model_id = job_id
        preview_url = None
        try:
            built = BrickModel.from_dict(result["model"])
            thumbnail(built).save(STORE.preview_path(model_id))
            preview_url = "/api/models/%s/preview" % model_id
        except Exception:
            # A missing thumbnail is a cosmetic loss, not a failed build.
            log.warning("could not render a preview for %s", model_id)

        STORE.save_model(model_id, {
            "model": result["model"], "summary": result["summary"],
            "status": "draft", "references": session["paths"],
            "thumbnail": preview_url,
            "owner": session.get("owner") or _client(request),
        })
        STORE.save_job({"id": job_id, "status": "done", "stage": "done",
                        "message": "Your set is ready.", "progress": 1.0,
                        "model_id": model_id, "summary": result["summary"],
                        "warnings": result["warnings"]})

    threading.Thread(target=run, daemon=True).start()
    return job


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

@app.get("/api/models")
def list_models(request: Request):
    """The caller's own sets.

    A set made before installs were told apart has no owner and is nobody's,
    so it is not listed. Opening one by its id still works: a link someone
    was given should not stop resolving.
    """
    return {"models": STORE.list_models(owner=_client(request))}


@app.get("/api/models/{model_id}")
def get_model(model_id: str):
    """Everything the app needs to show the set: model, parts, steps, price."""
    model = _load(model_id)
    return PIPELINE.package(model)


@app.get("/api/models/{model_id}/geometry")
def get_geometry(model_id: str):
    """Just the elements, for the 3D viewer.  Smaller than the full payload."""
    model = _load(model_id)
    colors = {cid: color_by_id(cid) for cid in model.color_ids}
    return {
        "fingerprint": model.fingerprint(),
        "size_studs": list(model.size_studs),
        "palette": {str(c.id): {"name": c.name, "hex": c.hex}
                    for c in colors.values()},
        "parts": {b.part_id: {"w": b.w, "d": b.d, "h": b.h,
                              "has_studs": b.has_studs}
                  for b in LIBRARY.all()},
        "bricks": [[b.part_id, b.color_id, b.x, b.y, b.z, b.rotation]
                   for b in model.bricks],
        "steps": [s.brick_indices for s in model.steps],
    }


@app.post("/api/models/{model_id}/edit")
def edit_model(model_id: str, body: dict):
    """Change an existing set. The set keeps its identity and gains a version.

    Nothing here generates a new model from scratch: a recolour edits the
    structured model in place, and a size or detail change rebuilds it from
    the same reference photos with different answers. Either way the parts
    list and the booklet are regenerated from the result, so they cannot
    drift from what the preview shows.
    """
    instruction = (body or {}).get("instruction", "")
    record = _record(model_id)
    answers = dict(record.get("model", {}).get("source", {}).get("answers", {}))

    plan = EDITOR.parse(instruction, answers)
    if plan.is_empty:
        raise HTTPException(
            422, "I couldn't tell what to change from that. Try something "
                 "like 'make it bigger', 'use fewer pieces' or 'make the "
                 "roof red'.")

    job_id = STORE.new_job()
    STORE.save_job({"id": job_id, "status": "building", "stage": "planning",
                    "message": "Applying your changes...", "progress": 0.15,
                    "plan": plan.to_dict(), "model_id": model_id})

    def run():
        try:
            if plan.needs_rebuild:
                result = _rebuild(record, plan, answers, job_id)
            else:
                result = _recolour(record, plan)
        except (EmptySilhouetteError, UnbuildableError,
                InconsistentModelError, NoUsableReferenceError) as exc:
            STORE.save_job({"id": job_id, "status": "failed", "error": str(exc),
                            "recoverable": True, "progress": 1.0,
                            "plan": plan.to_dict()})
            return
        except Exception:
            log.exception("edit failed")
            STORE.save_job({"id": job_id, "status": "failed",
                            "error": "The change could not be applied.",
                            "recoverable": True, "progress": 1.0,
                            "plan": plan.to_dict()})
            return

        STORE.save_job({"id": job_id, "status": "done", "stage": "done",
                        "message": "Your set has been updated.", "progress": 1.0,
                        "model_id": model_id, "summary": result["summary"],
                        "plan": plan.to_dict(),
                        "warnings": result.get("warnings", [])})

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id, "model_id": model_id, "plan": plan.to_dict()}


def _rebuild(record: dict, plan, answers: dict, job_id: str) -> dict:
    """Run the pipeline again over the same photos with changed answers."""
    paths = record.get("references") or []
    if not paths or not all(os.path.exists(p) for p in paths):
        raise NoUsableReferenceError(
            "The original photos are no longer available, so this set cannot "
            "be resized. Creating a new set from the photo will work.")

    def emit(stage, message, progress):
        STORE.save_job({"id": job_id, "status": "building", "stage": stage,
                        "message": message, "progress": progress,
                        "plan": plan.to_dict(),
                        "model_id": record["id"]})

    analysis, views = PIPELINE.analyze(paths)
    result = PIPELINE.build(views, analysis, EDITOR.answers_for(plan, answers),
                            emit)
    _save_version(record, result, plan)
    return result


def _recolour(record: dict, plan) -> dict:
    """Repaint part of the model without moving anything."""
    model = BrickModel.from_dict(record["model"])
    changed = EDITOR.recolour(model, plan.recolour)

    # Moving no bricks cannot break the structure, but the claim is cheap to
    # check and expensive to be wrong about, so it is checked.
    report = PIPELINE.validator.validate_and_repair(model)
    if not report.ok:
        raise UnbuildableError("The recoloured model no longer validates.",
                               report.to_dict())
    PIPELINE.instructions.generate(model)
    result = PIPELINE.package(model)
    result["warnings"] = (["Nothing matched that part of the model."]
                          if changed == 0 else [])
    _save_version(record, result, plan)
    return result


def _save_version(record: dict, result: dict, plan) -> None:
    """Keep the set's identity and its history; replace its current model."""
    versions = list(record.get("versions", []))
    versions.append({
        "fingerprint": record.get("model", {}).get("fingerprint"),
        "piece_count": record.get("summary", {}).get("piece_count"),
        "at": record.get("updated_at"),
        "change": ", ".join(plan.understood) or "edited",
    })
    record["model"] = result["model"]
    record["summary"] = result["summary"]
    record["versions"] = versions[-20:]
    try:
        thumbnail(BrickModel.from_dict(result["model"])).save(
            STORE.preview_path(record["id"]))
    except Exception:
        log.warning("could not refresh the preview for %s", record["id"])
    STORE.save_model(record["id"], record)


@app.get("/api/models/{model_id}/versions")
def get_versions(model_id: str):
    record = _record(model_id)
    return {"current": record.get("summary", {}),
            "versions": list(reversed(record.get("versions", [])))}


@app.get("/api/models/{model_id}/preview")
def get_preview(model_id: str):
    """A rendered still of the model, for lists and sharing."""
    path = STORE.preview_path(model_id)
    if not os.path.exists(path):
        # Older models predate previews; draw one now rather than 404.
        try:
            thumbnail(_load(model_id)).save(path)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(404, "No preview for this model.") from None
    return FileResponse(path, media_type="image/png")


@app.get("/api/models/{model_id}/parts")
def get_parts(model_id: str):
    model = _load(model_id)
    summary = PIPELINE.inventory.summary(model)
    lines = PIPELINE.inventory.bill_of_materials(model)
    summary["mismatches"] = PIPELINE.inventory.reconcile(model, lines)
    summary["unavailable"] = PIPELINE.inventory.check_availability(lines)
    return summary


@app.get("/api/models/{model_id}/steps")
def get_steps(model_id: str):
    model = _load(model_id)
    return {"steps": PIPELINE.instructions.describe(model),
            "fingerprint": model.fingerprint()}


@app.post("/api/models/{model_id}/price")
def price_model(model_id: str, body: dict = None):
    model = _load(model_id)
    shipping = (body or {}).get("shipping", "standard")
    lines = PIPELINE.inventory.bill_of_materials(model)
    return PIPELINE.pricing.price(lines, model.weight_g, shipping)


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------

@app.post("/api/orders")
def create_order(body: dict):
    model_id = (body or {}).get("model_id")
    if not model_id:
        raise HTTPException(400, "Which model is this order for?")
    model = _load(model_id)

    lines = PIPELINE.inventory.bill_of_materials(model)
    mismatch = PIPELINE.inventory.reconcile(model, lines)
    if mismatch:
        # Refuse rather than ship a box that does not match the instructions.
        raise HTTPException(
            409, "This model and its parts list disagree; it cannot be ordered.")
    short = PIPELINE.inventory.check_availability(lines)
    if short:
        raise HTTPException(
            409, "Some parts are out of stock: %s"
                 % ", ".join("%s %s" % (s["color_name"], s["part_name"])
                             for s in short[:3]))

    price = PIPELINE.pricing.price(lines, model.weight_g,
                                   (body or {}).get("shipping", "standard"))
    order = ORDERS.create(model_id, model.fingerprint(), price,
                          model.piece_count, lines)
    payment = ORDERS.begin_payment(order)
    return {"order": order.to_dict(), "payment": payment}


@app.get("/api/orders")
def list_orders():
    # Web-store orders carry a customer's address and are only readable with
    # their own link (see storefront.py), so they are not listed here.
    return {"orders": [o for o in STORE.list_orders()
                       if not o.get("access_token")]}


@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    try:
        order = STORE.get_order(order_id)
    except NotFound:
        raise HTTPException(404, "No such order.") from None
    if order.access_token:
        raise HTTPException(404, "No such order.")
    return order.to_dict()


@app.post("/api/orders/{order_id}/status")
def advance_order(order_id: str, body: dict):
    """Operations endpoint: move an order along its track."""
    status = (body or {}).get("status")
    if status not in STATUSES:
        raise HTTPException(400, "Status must be one of: %s" % ", ".join(STATUSES))
    try:
        if STORE.get_order(order_id).access_token:
            # Web orders move with their supplier, via /api/admin.
            raise HTTPException(404, "No such order.")
        return ORDERS.advance(order_id, status).to_dict()
    except NotFound:
        raise HTTPException(404, "No such order.") from None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _record(model_id: str) -> dict:
    try:
        return STORE.get_model(model_id)
    except NotFound:
        raise HTTPException(404, "No such model.") from None


def _load(model_id: str) -> BrickModel:
    try:
        return STORE.load_brick_model(model_id)
    except NotFound:
        raise HTTPException(404, "No such model.") from None


def _ext(filename: str | None) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".webp", ".heic") else ".jpg"


def _sweep_sessions(max_age: float = 3600.0) -> None:
    cutoff = time.time() - max_age
    for key in [k for k, v in _SESSIONS.items() if v["at"] < cutoff]:
        _SESSIONS.pop(key, None)


@app.exception_handler(NotFound)
def handle_not_found(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.get("/health")
def health():
    return {"ok": True, "vision": bool(SETTINGS.anthropic_api_key),
            "parts": len(LIBRARY.all())}


# ---------------------------------------------------------------------------
# the web store: same engine, same store, its own routes (storefront.py)
# ---------------------------------------------------------------------------

from . import storefront  # noqa: E402
from .examples import install_examples  # noqa: E402

storefront.bind(STORE, PIPELINE, ORDERS)
app.include_router(storefront.router)
install_examples(STORE)
storefront.mount_web(app)       # last: it answers every path nothing else did
