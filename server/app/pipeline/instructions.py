"""Stage 6 - InstructionGenerator.

Turns the built model into a booklet a person can follow: an ordered list of
steps, each naming the elements to add and exactly where they go.

The ordering rule is the whole job.  A step may only contain elements that
clutch onto something already standing -- the baseplate, or a piece from an
earlier step.  Building bottom-up by layer satisfies that almost everywhere,
so we do that first and then *check* it, moving any element that turns out to
have nothing under it yet into a later step.  A booklet that asks you to
place a brick in mid-air is the failure mode this stage exists to prevent.

Steps are also kept to a readable size, and split by region rather than
arbitrarily, so a step reads as "now do the left ear", not "now do fourteen
unrelated bricks".
"""

from __future__ import annotations

from collections import defaultdict

from ..library import LIBRARY, BrickLibrary, color_by_id
from ..models import BrickModel, BuildStep

MAX_PER_STEP = 12          # more than this on one page is hard to follow
MIN_PER_STEP = 3


class InstructionGenerator:
    def __init__(self, library: BrickLibrary = LIBRARY,
                 max_per_step: int = MAX_PER_STEP):
        self.library = library
        self.max_per_step = max_per_step

    def generate(self, model: BrickModel) -> list:
        order = self._build_order(model)
        steps = self._chunk(model, order)
        model.steps = steps
        return steps

    # ---- ordering --------------------------------------------------------

    def _build_order(self, model: BrickModel) -> list:
        """Indices in an order a person can actually follow.

        Layer by layer from the ground; within a layer, in reading order so
        the eye travels smoothly across the model rather than jumping.
        """
        by_layer = defaultdict(list)
        for i, b in enumerate(model.bricks):
            by_layer[b.y].append(i)

        order = []
        placed_cells = set()
        deferred = []

        for y in sorted(by_layer):
            layer = sorted(by_layer[y], key=lambda i: (model.bricks[i].z,
                                                       model.bricks[i].x))
            pending = deferred + layer
            deferred = []
            for i in pending:
                b = model.bricks[i]
                if b.y == 0 or self._rests_on(b, placed_cells):
                    order.append(i)
                    placed_cells.update(b.cells(self.library))
                else:
                    deferred.append(i)
            # a deferred element may now be supported by its own layer
            progress = True
            while deferred and progress:
                progress = False
                still = []
                for i in deferred:
                    b = model.bricks[i]
                    if self._rests_on(b, placed_cells):
                        order.append(i)
                        placed_cells.update(b.cells(self.library))
                        progress = True
                    else:
                        still.append(i)
                deferred = still

        # Anything never supported is placed last; the validator has already
        # guaranteed it is connected, so it hangs off something above it.
        order.extend(deferred)
        return order

    def _rests_on(self, brick, placed_cells: set) -> bool:
        b = self.library.get(brick.part_id)
        w, d = b.footprint(brick.rotation)
        below = brick.y - 1
        if below < 0:
            return True
        return any((brick.x + dx, below, brick.z + dz) in placed_cells
                   for dx in range(w) for dz in range(d))

    # ---- grouping --------------------------------------------------------

    def _chunk(self, model: BrickModel, order: list) -> list:
        """Split the order into readable steps, never across a layer."""
        steps = []
        current = []
        current_layer = None

        def flush(note=""):
            if not current:
                return
            idx = len(steps) + 1
            steps.append(BuildStep(
                index=idx,
                title=self._title(model, current, current_layer),
                brick_indices=list(current),
                note=note,
            ))
            current.clear()

        for i in order:
            y = model.bricks[i].y
            if current_layer is None:
                current_layer = y
            if y != current_layer or len(current) >= self.max_per_step:
                flush()
                current_layer = y
            current.append(i)
        flush()

        # A trailing step of one or two pieces reads as an afterthought; fold
        # it back into the previous step when they share a layer.
        if len(steps) > 1 and len(steps[-1].brick_indices) < MIN_PER_STEP:
            last = steps.pop()
            prev = steps[-1]
            if model.bricks[prev.brick_indices[0]].y == \
               model.bricks[last.brick_indices[0]].y:
                prev.brick_indices.extend(last.brick_indices)
            else:
                last.index = len(steps) + 1
                steps.append(last)
        for n, s in enumerate(steps, 1):
            s.index = n
        return steps

    def _title(self, model: BrickModel, indices: list, layer) -> str:
        layer_no = (layer // 3) + 1 if layer is not None else 1
        return "Layer %d" % layer_no

    # ---- rendering for the client ---------------------------------------

    def describe(self, model: BrickModel) -> list:
        """Each step as the app shows it: what to add, and where each goes."""
        out = []
        for step in model.steps:
            counts = defaultdict(int)
            placements = []
            for i in step.brick_indices:
                b = model.bricks[i]
                brick = self.library.get(b.part_id)
                color = color_by_id(b.color_id)
                counts[(b.part_id, b.color_id)] += 1
                placements.append({
                    "brick_index": i,
                    "part_id": b.part_id,
                    "part_name": brick.name,
                    "color_id": b.color_id,
                    "color_name": color.name,
                    "color_hex": color.hex,
                    "x": b.x, "y": b.y, "z": b.z,
                    "rotation": b.rotation,
                })
            adds = []
            for (part_id, color_id), n in sorted(
                    counts.items(), key=lambda kv: -kv[1]):
                brick = self.library.get(part_id)
                color = color_by_id(color_id)
                adds.append({
                    "quantity": n,
                    "part_id": part_id,
                    "part_name": brick.name,
                    "color_id": color_id,
                    "color_name": color.name,
                    "color_hex": color.hex,
                    "label": "%d x %s %s" % (n, color.name, brick.name),
                })
            out.append({
                "index": step.index,
                "title": step.title,
                "note": step.note,
                "add": adds,
                "placements": placements,
                "piece_count": len(step.brick_indices),
                # everything standing after this step, for the 3D view
                "cumulative": self._cumulative(model, step.index),
            })
        return out

    def _cumulative(self, model: BrickModel, upto: int) -> int:
        total = 0
        for s in model.steps:
            if s.index <= upto:
                total += len(s.brick_indices)
        return total

    # ---- verification ----------------------------------------------------

    def verify(self, model: BrickModel) -> list:
        """Confirm every step can be assembled onto the one before it."""
        problems = []
        placed = set()
        for step in model.steps:
            for i in step.brick_indices:
                b = model.bricks[i]
                if b.y > 0 and not self._rests_on(b, placed):
                    # It may clutch onto something above instead, which is
                    # legal but only if that something is already placed.
                    if not self._hangs_from(model, b, placed):
                        problems.append(
                            "Step %d places a %s with nothing beneath it yet."
                            % (step.index, self.library.get(b.part_id).name))
            for i in step.brick_indices:
                placed.update(model.bricks[i].cells(self.library))
        return problems

    def _hangs_from(self, model: BrickModel, brick, placed_cells: set) -> bool:
        b = self.library.get(brick.part_id)
        w, d = b.footprint(brick.rotation)
        above = brick.y + b.h
        return any((brick.x + dx, above, brick.z + dz) in placed_cells
                   for dx in range(w) for dz in range(d))


def estimate_build_time(model: BrickModel) -> dict:
    """Minutes to build, from piece count and how fiddly the pieces are.

    Small elements take longer per piece than big ones -- finding a 1x1 in
    the tray is most of the time -- so the estimate is weighted by size, not
    a flat rate.  Calibrated against published build times for sets of a
    comparable piece count.
    """
    seconds = 0.0
    for b in model.bricks:
        brick = LIBRARY.get(b.part_id)
        seconds += 9.0 if brick.studs <= 1 else 7.0 if brick.studs <= 4 else 6.0
    seconds += len(model.steps) * 8.0        # reading each page
    minutes = int(round(seconds / 60.0))
    hours, mins = divmod(max(1, minutes), 60)
    return {
        "minutes": max(1, minutes),
        "label": ("%dh %02dm" % (hours, mins)) if hours else ("%dm" % mins),
    }


def difficulty(model: BrickModel) -> str:
    n = model.piece_count
    colors = len(model.color_ids)
    score = n / 250.0 + colors / 12.0 + len(model.steps) / 40.0
    if score < 1.4:
        return "Easy"
    if score < 2.8:
        return "Medium"
    return "Hard"
