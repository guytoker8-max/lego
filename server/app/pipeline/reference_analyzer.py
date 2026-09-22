"""Stage 1 - ReferenceAnalyzer.

Looks at the photos the user gave us and reports what we are about to build:
the subject, its proportions, its symmetry, how deep it probably is, what it
is made of, and -- importantly -- what we could not tell, so stage 4 can ask
the user instead of guessing.

Two sources, in order:

1. A vision model (Claude), which names the subject and judges depth and
   structure the way a person would.  Server-side key; never the client's.
2. Plain computer vision, which always runs.  It supplies the silhouette and
   the colours either way, and stands in for the whole analysis when no key
   is configured or the call fails.

The CV pass is not a stub.  A model built from it alone is still a real,
buildable model -- it just gets a generic name and a conservative depth.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os

import numpy as np
from PIL import Image

from ..models import Analysis
from . import imaging

log = logging.getLogger(__name__)

VISION_MODEL = os.environ.get("BRICKSNAP_VISION_MODEL", "claude-sonnet-5")
BLUR_THRESHOLD = 60.0          # Laplacian variance below this reads as soft


class View:
    """One reference photo, already segmented."""

    def __init__(self, path, angle: str = "front"):
        self.path = str(path)
        self.angle = angle
        self.rgb = imaging.load_rgb(path)
        self.mask, self.blob_count = imaging.segment(self.rgb)
        self.rgb, self.mask = imaging.crop_to_mask(self.rgb, self.mask)
        self.sharpness = imaging.sharpness(self.rgb)

    @property
    def aspect(self) -> float:
        h, w = self.mask.shape
        return w / h if h else 1.0

    @property
    def coverage(self) -> float:
        return float(self.mask.mean())


class ReferenceAnalyzer:
    def __init__(self, api_key: str | None = None, model: str = VISION_MODEL):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model

    # ---- entry point -----------------------------------------------------

    def analyze(self, paths: list, angles: list | None = None) -> tuple:
        """Return (Analysis, [View]).  Never raises on a bad photo."""
        angles = angles or ["front", "side", "back", "top"]
        views = []
        for i, p in enumerate(paths):
            try:
                views.append(View(p, angles[i] if i < len(angles) else "other"))
            except Exception as exc:                      # unreadable upload
                log.warning("could not read reference %s: %s", p, exc)
        if not views:
            raise NoUsableReferenceError(
                "None of the uploaded images could be read as a photo.")

        analysis = self._heuristic(views)
        if self.api_key:
            try:
                self._apply_vision(analysis, views)
            except Exception as exc:
                log.warning("vision analysis unavailable, using CV only: %s", exc)
                analysis.warnings.append(
                    "Detailed analysis was unavailable, so the shape was read "
                    "from the photo's outline only.")
        analysis.questions = self._questions(analysis, views)
        return analysis, views

    # ---- computer vision -------------------------------------------------

    def _heuristic(self, views: list) -> Analysis:
        front = views[0]
        sym = imaging.symmetry_score(front.mask)
        blobs = front.blob_count
        colors = imaging.dominant_colors(front.rgb, front.mask)

        warnings = []
        if front.sharpness < BLUR_THRESHOLD:
            warnings.append(
                "This photo is quite soft, so fine detail may not survive the "
                "conversion to bricks.")
        if front.coverage < 0.06:
            warnings.append(
                "The subject fills only a small part of the frame; a closer "
                "photo would give a sharper model.")
        if blobs > 1:
            warnings.append(
                "There looks to be more than one object in the photo. The "
                "largest one was used.")

        return Analysis(
            subject="model",
            display_name="Your Model",
            description="",
            symmetry="left-right" if sym > 0.82 else "none",
            depth_profile="rounded",
            depth_ratio=0.55,
            components=[],
            dominant_colors=[{"rgb": list(c), "share": round(s, 3)}
                             for c, s in colors],
            confidence=0.35,
            warnings=warnings,
            source="heuristic",
        )

    # ---- vision ----------------------------------------------------------

    def _apply_vision(self, analysis: Analysis, views: list) -> None:
        data = self._ask_vision(views)
        analysis.subject = data.get("subject", analysis.subject)
        analysis.display_name = data.get("display_name") or analysis.display_name
        analysis.description = data.get("description", "")
        analysis.components = data.get("components", [])
        if data.get("symmetry") in ("none", "left-right", "radial"):
            analysis.symmetry = data["symmetry"]
        if data.get("depth_profile") in ("flat", "rounded", "boxy", "deep"):
            analysis.depth_profile = data["depth_profile"]
        try:
            ratio = float(data.get("depth_ratio", analysis.depth_ratio))
            analysis.depth_ratio = min(1.6, max(0.08, ratio))
        except (TypeError, ValueError):
            pass
        analysis.confidence = min(1.0, max(0.0, float(data.get("confidence", 0.7))))
        analysis.warnings.extend(data.get("warnings", []) or [])
        analysis.source = "vision"

    def _ask_vision(self, views: list) -> dict:
        import httpx

        content = []
        for v in views[:4]:
            content.append({"type": "text", "text": "Reference (%s view):" % v.angle})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": _as_jpeg_b64(v.rgb)}})
        content.append({"type": "text", "text": _PROMPT})

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": self.model, "max_tokens": 1200,
                  "messages": [{"role": "user", "content": content}]},
            timeout=60.0,
        )
        resp.raise_for_status()
        text = "".join(part.get("text", "")
                       for part in resp.json().get("content", []))
        return _first_json_object(text)

    # ---- questions for the user -----------------------------------------

    def _questions(self, analysis: Analysis, views: list) -> list:
        """Only ask what actually changes the model, and never more than a few.

        Size and detail always change it.  The unseen-back question only
        matters when we have a single view of something with real depth.
        """
        qs = [
            {"id": "size", "prompt": "How large should the finished model be?",
             "options": [
                 {"id": "mini", "label": "Mini"},
                 {"id": "small", "label": "Small"},
                 {"id": "medium", "label": "Medium", "default": True},
                 {"id": "large", "label": "Large"},
             ]},
            {"id": "detail", "prompt": "Maximum detail, or fewer pieces?",
             "options": [
                 {"id": "detailed", "label": "Detailed"},
                 {"id": "balanced", "label": "Balanced", "default": True},
                 {"id": "simple", "label": "Simple"},
             ]},
            {"id": "priority",
             "prompt": "Should the model favour looks or strength?",
             "options": [
                 {"id": "appearance", "label": "Appearance"},
                 {"id": "balanced", "label": "Balanced", "default": True},
                 {"id": "strength", "label": "Strength"},
             ]},
        ]
        if len(views) == 1 and analysis.depth_profile != "flat":
            qs.append({
                "id": "unseen_back",
                "prompt": ("I can see the front, but not the back. Should I "
                           "create a reasonable interpretation of the unseen side?"),
                "options": [
                    {"id": "yes", "label": "Yes", "default": True},
                    {"id": "no", "label": "No, I'll add another photo"},
                ],
            })
        return qs


class NoUsableReferenceError(ValueError):
    """Every uploaded file failed to open as an image."""


_PROMPT = """You are the analysis stage of a pipeline that turns a photo into a
buildable brick model. Look at the reference photo(s) and answer as JSON only,
no prose, with exactly these keys:

{
  "subject": "short lowercase noun, e.g. golden retriever",
  "display_name": "Title Case name for the set, e.g. Golden Retriever",
  "description": "one sentence on the form and pose",
  "components": ["major parts, e.g. head, body, legs, tail"],
  "symmetry": "none" | "left-right" | "radial",
  "depth_profile": "flat" | "rounded" | "boxy" | "deep",
  "depth_ratio": number,   // depth front-to-back as a fraction of the width
  "confidence": number,    // 0-1, how sure you are of the 3D form
  "warnings": ["anything that will make this hard to build in bricks"]
}

Judge depth_ratio physically: a plate is about 0.1, a face mask 0.35, a car
0.45, a dog seen from the side 0.35, a dog seen head-on 1.2, a ball 1.0.
If the photo is blurry, crowded or ambiguous, say so in warnings and lower
confidence rather than inventing detail."""


def _as_jpeg_b64(rgb: np.ndarray, max_side: int = 640) -> str:
    img = Image.fromarray(rgb)
    if max(img.size) > max_side:
        s = max_side / max(img.size)
        img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def _first_json_object(text: str) -> dict:
    """Pull the first {...} out of a reply that may be wrapped in prose."""
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in vision reply")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object in vision reply")
