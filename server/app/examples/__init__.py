"""The sets on the homepage: real models, built by the real pipeline.

Each example is a source picture and the model the pipeline built from it,
saved as a fixture (``data/<slug>.json`` beside ``data/<slug>.png``).  They
are installed into the store at start-up under ``example-<slug>``, so the
homepage links straight into the same design page a customer's own set uses
-- 3D preview, parts list, price, booklet -- and nothing on the homepage is
a mock-up.

``scripts/make_examples.py`` rebuilds them from the source pictures.
"""

from __future__ import annotations

import json
import os

from fastapi import HTTPException
from fastapi.responses import FileResponse

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Display order on the homepage.
ORDER = ("pet", "car", "house", "person", "object")


def _load(slug: str) -> dict | None:
    path = os.path.join(DATA, "%s.json" % slug)
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def list_examples() -> list:
    out = []
    for slug in ORDER:
        rec = _load(slug)
        if not rec:
            continue
        m = rec["model"]
        out.append({
            "slug": slug,
            "title": rec.get("title", m["name"]),
            "caption": rec.get("caption", ""),
            "category": rec.get("category", slug),
            "model_id": "example-%s" % slug,
            "source": "/api/store/examples/%s/source.png" % slug,
            "thumbnail": "/api/models/example-%s/preview" % slug,
            "piece_count": m["piece_count"],
            "dimensions_cm": m["dimensions_cm"],
        })
    return out


def install_examples(store) -> int:
    """Put every example in the store, replacing any older copy."""
    n = 0
    for slug in ORDER:
        rec = _load(slug)
        if not rec:
            continue
        model_id = "example-%s" % slug
        try:
            current = store.get_model(model_id)
            if current.get("model", {}).get("fingerprint") == \
                    rec["model"]["fingerprint"]:
                n += 1
                continue
        except Exception:
            pass
        store.save_model(model_id, {
            "model": rec["model"], "summary": rec["summary"],
            "status": "example", "example": True, "references": [],
            "thumbnail": "/api/models/%s/preview" % model_id,
            "web": {"category": rec.get("category"), "size": rec.get("size"),
                    "photos": [{"url": "/api/store/examples/%s/source.png" % slug,
                                "name": "example picture"}]},
        })
        n += 1
    return n


def source_response(slug: str):
    path = os.path.join(DATA, "%s.png" % slug)
    if slug not in ORDER or not os.path.exists(path):
        raise HTTPException(404, "No such example.")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
