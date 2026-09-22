"""Phase 3 - ModelEditor: changing a set that already exists.

"Make it bigger." "Use fewer pieces." "Make the roof red." "Make it stronger."

The brief is emphatic about what must *not* happen here: an edit may not
generate a fresh, unrelated model. It changes the structured model -- or
rebuilds it from the same reference photos with different parameters -- and
then everything downstream is regenerated from the result, so the preview,
the parts list, the booklet and the price stay the same object.

Two kinds of edit, and the difference matters:

*Recolour* touches the model directly. Nothing moves, so the structure is
untouched and validation cannot newly fail -- but it is re-run anyway,
because "cannot fail" is a claim better checked than trusted.

*Rebuild* changes the geometry -- size, detail level, strength -- and there
is no way to do that to a finished model: a bigger model is not a scaled
version of a smaller one, it is a different tiling of a finer grid. So the
pipeline runs again from the stored reference photos with the answers
changed. That is why the references are kept with the model.

Instructions are parsed by Claude where a key is configured, and by keyword
otherwise. The fallback is not a toy: the phrases people actually use for
this are few and blunt, and the parser reports what it understood so the
user can see whether it got them right.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict

from ..config import PRESETS_BY_KEY, SIZE_PRESETS
from ..library import DEFAULT_COLORS, color_by_id
from ..models import BrickModel, PlacedBrick

log = logging.getLogger(__name__)

SIZE_ORDER = [p.key for p in SIZE_PRESETS]
DETAIL_ORDER = ["simple", "balanced", "detailed"]
PRIORITY_ORDER = ["appearance", "balanced", "strength"]

# Where on the model an instruction is pointing. Not semantic segmentation --
# it is honest about being geometric, and "the roof" really is the top of the
# model, which is what people mean.
REGIONS = {
    "roof": "top", "top": "top", "head": "top", "lid": "top",
    "base": "bottom", "bottom": "bottom", "floor": "bottom", "feet": "bottom",
    "front": "front", "face": "front",
    "back": "back", "rear": "back",
    "left": "left", "right": "right",
    "middle": "middle", "centre": "middle", "center": "middle", "body": "middle",
    "all": "all", "whole": "all", "everything": "all",
}


@dataclass
class EditPlan:
    """What an instruction was understood to mean."""

    size: str | None = None
    detail: str | None = None
    priority: str | None = None
    recolour: list = field(default_factory=list)   # [{region, color_id}]
    understood: list = field(default_factory=list)
    not_understood: list = field(default_factory=list)

    @property
    def needs_rebuild(self) -> bool:
        return any((self.size, self.detail, self.priority))

    @property
    def is_empty(self) -> bool:
        return not self.needs_rebuild and not self.recolour

    def to_dict(self) -> dict:
        d = asdict(self)
        d["needs_rebuild"] = self.needs_rebuild
        return d


class ModelEditor:
    def __init__(self, api_key: str | None = None, colors=DEFAULT_COLORS):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.colors = colors

    # ---- understanding the request --------------------------------------

    def parse(self, instruction: str, current: dict) -> EditPlan:
        text = (instruction or "").strip()
        if not text:
            return EditPlan(not_understood=["Nothing to change."])
        if self.api_key:
            try:
                return self._parse_with_model(text, current)
            except Exception as exc:
                log.warning("edit parsing fell back to keywords: %s", exc)
        return self._parse_keywords(text, current)

    def _parse_keywords(self, text: str, current: dict) -> EditPlan:
        low = text.lower()
        plan = EditPlan()

        size_now = current.get("size", "medium")
        if re.search(r"\b(bigger|larger|grow|scale up|more detail)\b", low):
            plan.size = _step(SIZE_ORDER, size_now, +1)
            plan.understood.append("make it bigger (%s)" % plan.size)
        elif re.search(r"\b(smaller|tinier|shrink|scale down)\b", low):
            plan.size = _step(SIZE_ORDER, size_now, -1)
            plan.understood.append("make it smaller (%s)" % plan.size)
        for preset in SIZE_ORDER:
            if re.search(r"\b%s\b" % preset, low):
                plan.size = preset
                plan.understood.append("size: %s" % preset)

        detail_now = current.get("detail", "balanced")
        if re.search(r"\b(fewer pieces|less pieces|simpler|simplify|easier to build|easier)\b", low):
            plan.detail = _step(DETAIL_ORDER, detail_now, -1)
            plan.understood.append("fewer pieces (%s)" % plan.detail)
        elif re.search(r"\b(more detail|more detailed|finer|sharper)\b", low):
            plan.detail = _step(DETAIL_ORDER, detail_now, +1)
            plan.understood.append("more detail (%s)" % plan.detail)

        priority_now = current.get("priority", "balanced")
        if re.search(r"\b(stronger|sturdier|solid|robust|tougher)\b", low):
            plan.priority = "strength"
            plan.understood.append("build it stronger")
        elif re.search(r"\b(prettier|nicer|better looking|appearance)\b", low):
            plan.priority = "appearance"
            plan.understood.append("favour appearance")

        for region, color_id in self._find_recolours(low):
            plan.recolour.append({"region": region, "color_id": color_id})
            plan.understood.append(
                "make the %s %s" % (region, color_by_id(color_id).name))

        if not plan.understood:
            plan.not_understood.append(text)
        return plan

    def _find_recolours(self, low: str) -> list:
        """Match '<region> <colour>' pairs against real brick colours.

        Clause by clause, because "the base dark blue and the top yellow" is
        two requests and scanning the whole sentence for a colour gives both
        regions the first one.
        """
        found = []
        seen = set()
        for clause in re.split(r"\band\b|[,;.]", low):
            region = self._region_in(clause)
            if region is None or region in seen:
                continue
            cid = self._color_in(clause)
            if cid is None:
                continue
            seen.add(region)
            found.append((region, cid))
        if found:
            return found

        # No clause carried both. Fall back to one region and one colour
        # found anywhere, which covers "paint the roof red please".
        region = self._region_in(low)
        cid = self._color_in(low)
        if region is not None and cid is not None:
            return [(region, cid)]
        return []

    def _region_in(self, text: str) -> str | None:
        for word in sorted(REGIONS, key=len, reverse=True):
            if re.search(r"\b%s\b" % word, text):
                return REGIONS[word]
        return None

    def _color_in(self, text: str) -> int | None:
        names = sorted(((c.name.lower(), c.id) for c in self.colors.colors),
                       key=lambda t: -len(t[0]))
        for name, cid in names:
            if re.search(r"\b%s\b" % re.escape(name), text):
                return cid
        # Bare colour words people use that are not the catalogue name
        for word, cid in sorted(_COMMON_COLOR_WORDS.items(),
                                key=lambda t: -len(t[0])):
            if re.search(r"\b%s\b" % word, text) and self.colors.exists(cid):
                return cid
        return None

    def _parse_with_model(self, text: str, current: dict) -> EditPlan:
        import httpx

        palette = ", ".join("%s (%d)" % (c.name, c.id) for c in self.colors.colors)
        prompt = _PARSE_PROMPT % {
            "instruction": text,
            "size": current.get("size", "medium"),
            "detail": current.get("detail", "balanced"),
            "priority": current.get("priority", "balanced"),
            "sizes": ", ".join(SIZE_ORDER),
            "regions": ", ".join(sorted(set(REGIONS.values()))),
            "palette": palette,
        }
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": os.environ.get("BRICKSNAP_VISION_MODEL", "claude-sonnet-5"),
                  "max_tokens": 700,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=40.0,
        )
        resp.raise_for_status()
        body = "".join(part.get("text", "")
                       for part in resp.json().get("content", []))
        data = _first_json_object(body)

        plan = EditPlan(understood=list(data.get("understood", [])),
                        not_understood=list(data.get("not_understood", [])))
        if data.get("size") in SIZE_ORDER:
            plan.size = data["size"]
        if data.get("detail") in DETAIL_ORDER:
            plan.detail = data["detail"]
        if data.get("priority") in PRIORITY_ORDER:
            plan.priority = data["priority"]
        for item in data.get("recolour", []) or []:
            region = item.get("region")
            cid = item.get("color_id")
            # The model may name a colour we do not stock; drop it rather
            # than order something nobody can supply.
            if region in set(REGIONS.values()) and self.colors.exists(cid):
                plan.recolour.append({"region": region, "color_id": int(cid)})
        return plan

    # ---- applying it -----------------------------------------------------

    def recolour(self, model: BrickModel, changes: list) -> int:
        """Repaint part of the model. Returns how many elements changed."""
        if not model.bricks:
            return 0
        bounds = _bounds(model)
        changed = 0
        for change in changes:
            region = change["region"]
            cid = int(change["color_id"])
            if not self.colors.exists(cid):
                continue
            for i, b in enumerate(model.bricks):
                if _in_region(b, region, bounds, model):
                    if b.color_id != cid:
                        model.bricks[i] = PlacedBrick(
                            b.part_id, cid, b.x, b.y, b.z, b.rotation)
                        changed += 1
        return changed

    def answers_for(self, plan: EditPlan, current: dict) -> dict:
        """The build answers a rebuild should use."""
        answers = dict(current)
        if plan.size:
            answers["size"] = plan.size
        if plan.detail:
            answers["detail"] = plan.detail
        if plan.priority:
            answers["priority"] = plan.priority
        return answers


# ---------------------------------------------------------------------------
# regions
# ---------------------------------------------------------------------------

def _bounds(model: BrickModel) -> dict:
    xs = [b.x for b in model.bricks]
    ys = [b.y for b in model.bricks]
    zs = [b.z for b in model.bricks]
    return {"x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
            "z0": min(zs), "z1": max(zs)}


def _in_region(brick: PlacedBrick, region: str, b: dict,
               model: BrickModel) -> bool:
    """A third of the model in the named direction; 'all' is everything."""
    if region == "all":
        return True
    span_y = max(1, b["y1"] - b["y0"])
    span_x = max(1, b["x1"] - b["x0"])
    span_z = max(1, b["z1"] - b["z0"])
    if region == "top":
        return brick.y >= b["y0"] + span_y * 2 / 3
    if region == "bottom":
        return brick.y <= b["y0"] + span_y / 3
    if region == "middle":
        return b["y0"] + span_y / 3 < brick.y < b["y0"] + span_y * 2 / 3
    if region == "left":
        return brick.x <= b["x0"] + span_x / 3
    if region == "right":
        return brick.x >= b["x0"] + span_x * 2 / 3
    if region == "front":
        return brick.z <= b["z0"] + span_z / 3
    if region == "back":
        return brick.z >= b["z0"] + span_z * 2 / 3
    return False


def _step(order: list, current: str, by: int) -> str:
    try:
        i = order.index(current)
    except ValueError:
        i = len(order) // 2
    return order[max(0, min(len(order) - 1, i + by))]


_COMMON_COLOR_WORDS = {
    "red": 4, "blue": 1, "green": 2, "yellow": 14, "white": 15, "black": 0,
    "grey": 71, "gray": 71, "orange": 25, "brown": 70, "tan": 19,
    "purple": 85, "pink": 29, "lime": 27, "azure": 321,
}

_PARSE_PROMPT = """A user wants to change a brick model they already have.
Their model is currently size=%(size)s, detail=%(detail)s, priority=%(priority)s.

Their instruction: "%(instruction)s"

Answer as JSON only, with these keys:
{
  "size": one of [%(sizes)s] or null,
  "detail": "simple" | "balanced" | "detailed" or null,
  "priority": "appearance" | "balanced" | "strength" or null,
  "recolour": [{"region": one of [%(regions)s], "color_id": number}],
  "understood": ["plain restatement of each change you applied"],
  "not_understood": ["any part of the request you could not map"]
}

Set a field to null when the instruction does not ask to change it. Colours
must be chosen from this palette by id: %(palette)s
Regions are geometric thirds of the model, so "roof" means the top third.
If the request asks for something this cannot express -- adding a feature,
changing the subject -- put it in not_understood rather than approximating."""


def _first_json_object(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object")
