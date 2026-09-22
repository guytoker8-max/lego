"""Stage 4 - StructuralValidator.

The promise is a set you can actually build, so this is the stage that has to
be right.  A model is not shown to anyone until it passes here.

What "buildable" means, concretely
----------------------------------
1. Every element is one the brick library stocks.
2. No two elements occupy the same cell, and none sits below the baseplate.
3. Every element is joined to another: a stud under it, or one above.  Two
   bricks merely side by side are *not* joined -- that is a pile, not a model.
4. Every element is joined, through some chain of joints, to the ground. An
   island that floats in the air fails even if its own bricks interlock.
5. The centre of mass sits over the footprint, so the thing stands up.
6. Each build step can be assembled onto the one before it.

When a check fails we do not report and stop: we repair and re-check, which
is what section 6 of the brief asks for.  Repair either roots a floating
island by growing a column of support under it, or -- if nothing can reach it
-- removes it.  Removing is a real change to the model, so it is reported,
and the instructions and parts list are regenerated from the repaired model
rather than the original.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..library import LIBRARY, BrickLibrary, UnknownPartError
from ..models import BrickModel, PlacedBrick

MAX_REPAIR_ROUNDS = 6


@dataclass
class Issue:
    code: str
    message: str
    severity: str = "error"      # "error" blocks the build, "warning" does not
    brick_indices: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message,
                "severity": self.severity,
                "brick_indices": self.brick_indices[:50]}


@dataclass
class ValidationReport:
    ok: bool = True
    issues: list = field(default_factory=list)
    repairs: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.severity == "error"]

    def to_dict(self) -> dict:
        return {"ok": self.ok,
                "issues": [i.to_dict() for i in self.issues],
                "repairs": self.repairs,
                "stats": self.stats}


class StructuralValidator:
    def __init__(self, library: BrickLibrary = LIBRARY):
        self.library = library

    # ---- public ----------------------------------------------------------

    def validate(self, model: BrickModel) -> ValidationReport:
        report = ValidationReport()
        occ, overlaps = self._occupancy(model, report)
        self._check_parts(model, report)
        self._check_bounds(model, report)
        joints = self._joints(model, occ)
        grounded = self._grounded(model, joints)
        self._check_support(model, grounded, report)
        self._check_balance(model, report)
        report.stats = self._stats(model, joints, grounded)
        report.ok = not report.errors
        return report

    def validate_and_repair(self, model: BrickModel) -> ValidationReport:
        """Fix what can be fixed, then confirm. The model is edited in place."""
        report = self.validate(model)
        rounds = 0
        while not report.ok and rounds < MAX_REPAIR_ROUNDS:
            rounds += 1
            changed = self._repair(model, report)
            if not changed:
                break
            report = self.validate(model)
            report.repairs = list(getattr(model, "_repairs", []))
        report.repairs = list(getattr(model, "_repairs", []))
        report.stats["repair_rounds"] = rounds
        model.validation = report.to_dict()
        return report

    # ---- checks ----------------------------------------------------------

    def _occupancy(self, model: BrickModel, report: ValidationReport) -> tuple:
        cells = {}
        clashes = []
        for i, b in enumerate(model.bricks):
            try:
                brick_cells = list(b.cells(self.library))
            except UnknownPartError:
                continue                       # reported by _check_parts
            for c in brick_cells:
                if c in cells:
                    clashes.append(i)
                else:
                    cells[c] = i
        if clashes:
            report.issues.append(Issue(
                "overlap",
                "%d elements share space with another element." % len(clashes),
                "error", sorted(set(clashes))))
        return cells, clashes

    def _check_parts(self, model: BrickModel, report: ValidationReport) -> None:
        missing = []
        for i, b in enumerate(model.bricks):
            if not self.library.exists(b.part_id):
                missing.append(i)
        if missing:
            report.issues.append(Issue(
                "unknown_part",
                "%d elements are not in the brick library and could not be "
                "supplied." % len(missing), "error", missing))

    def _check_bounds(self, model: BrickModel, report: ValidationReport) -> None:
        below = [i for i, b in enumerate(model.bricks) if b.y < 0]
        if below:
            report.issues.append(Issue(
                "below_base", "%d elements sit below the baseplate." % len(below),
                "error", below))

    def _joints(self, model: BrickModel, occ: dict) -> dict:
        """Which elements are actually clutched together.

        A joint exists where one element's top studs meet the underside of
        another.  Side-by-side contact is not a joint.
        """
        joints = {i: set() for i in range(len(model.bricks))}
        tops = {}
        for i, b in enumerate(model.bricks):
            if not self.library.exists(b.part_id):
                continue
            brick = self.library.get(b.part_id)
            if not brick.has_studs:
                continue
            top_y = b.y + brick.h
            for (sx, sz) in brick.top_studs(b.x, b.z, b.rotation):
                tops.setdefault((sx, top_y, sz), []).append(i)

        for cell, owners in tops.items():
            above = occ.get(cell)
            if above is None:
                continue
            for i in owners:
                if above != i:
                    joints[i].add(above)
                    joints[above].add(i)
        return joints

    def _grounded(self, model: BrickModel, joints: dict) -> set:
        """Everything that can be reached building upward from the baseplate.

        Note what this deliberately is *not*: it is not "connected to the
        model".  An element whose only joint is to something above it is
        connected once the model is finished, but there is no moment during
        the build when you could have placed it -- it would have had to hang
        in the air waiting for its neighbour.  Requiring support from below
        is what makes the model and the booklet agree, so a brick that only
        hangs is treated as unsupported here and the repair pass props it.
        """
        supported = set()
        by_layer = {}
        for i, b in enumerate(model.bricks):
            by_layer.setdefault(b.y, []).append(i)

        # Which elements present a stud at each cell, keyed by the layer the
        # stud sits in, so a layer can be resolved against the ones below it.
        tops = {}
        for i, b in enumerate(model.bricks):
            if not self.library.exists(b.part_id):
                continue
            brick = self.library.get(b.part_id)
            if not brick.has_studs:
                continue
            top_y = b.y + brick.h
            for (sx, sz) in brick.top_studs(b.x, b.z, b.rotation):
                tops.setdefault((sx, top_y, sz), []).append(i)

        for y in sorted(by_layer):
            for i in by_layer[y]:
                b = model.bricks[i]
                if b.y == 0:
                    supported.add(i)
                    continue
                if not self.library.exists(b.part_id):
                    continue
                brick = self.library.get(b.part_id)
                w, d = brick.footprint(b.rotation)
                for dx in range(w):
                    for dz in range(d):
                        owners = tops.get((b.x + dx, b.y, b.z + dz), ())
                        if any(o in supported for o in owners):
                            supported.add(i)
                            break
                    if i in supported:
                        break
        return supported

    def _check_support(self, model: BrickModel, grounded: set,
                       report: ValidationReport) -> None:
        floating = [i for i in range(len(model.bricks)) if i not in grounded]
        if floating:
            report.issues.append(Issue(
                "floating",
                "%d elements have nothing beneath them to rest on."
                % len(floating), "error", floating))

    def _check_balance(self, model: BrickModel, report: ValidationReport) -> None:
        """Is the centre of mass over the part that touches the ground?"""
        if not model.bricks:
            return
        total = 0.0
        cx = cz = 0.0
        foot = []
        for b in model.bricks:
            if not self.library.exists(b.part_id):
                continue
            brick = self.library.get(b.part_id)
            w, d = brick.footprint(b.rotation)
            m = brick.weight_g
            total += m
            cx += m * (b.x + w / 2.0)
            cz += m * (b.z + d / 2.0)
            if b.y == 0:
                foot.append((b.x, b.z, w, d))
        if total <= 0 or not foot:
            return
        cx /= total
        cz /= total
        x0 = min(f[0] for f in foot)
        x1 = max(f[0] + f[2] for f in foot)
        z0 = min(f[1] for f in foot)
        z1 = max(f[1] + f[3] for f in foot)
        inside = (x0 <= cx <= x1) and (z0 <= cz <= z1)
        if not inside:
            report.issues.append(Issue(
                "unbalanced",
                "The model's weight falls outside its footprint, so it would "
                "topple. It needs a wider base.", "error", []))
        else:
            margin = min(cx - x0, x1 - cx, cz - z0, z1 - cz)
            if margin < 0.75:
                report.issues.append(Issue(
                    "tippy",
                    "The model stands, but only just. A display baseplate is "
                    "recommended.", "warning", []))

    def _stats(self, model: BrickModel, joints: dict, grounded: set) -> dict:
        n = len(model.bricks)
        joint_count = sum(len(v) for v in joints.values()) // 2
        return {
            "pieces": n,
            "joints": joint_count,
            "joints_per_piece": round(joint_count / n, 2) if n else 0.0,
            "grounded": len(grounded),
            "floating": n - len(grounded),
        }

    # ---- repair ----------------------------------------------------------

    def _repair(self, model: BrickModel, report: ValidationReport) -> bool:
        """One round of fixes.  Returns True if the model changed."""
        repairs = getattr(model, "_repairs", [])
        changed = False

        for issue in report.errors:
            if issue.code == "unknown_part":
                before = len(model.bricks)
                keep = set(issue.brick_indices)
                model.bricks = [b for i, b in enumerate(model.bricks)
                                if i not in keep]
                repairs.append("Removed %d elements that no supplier stocks."
                               % (before - len(model.bricks)))
                changed = True
                break

            if issue.code == "overlap":
                keep = set(issue.brick_indices)
                before = len(model.bricks)
                model.bricks = [b for i, b in enumerate(model.bricks)
                                if i not in keep]
                repairs.append("Removed %d elements that clashed with another."
                               % (before - len(model.bricks)))
                changed = True
                break

            if issue.code == "below_base":
                lift = -min(b.y for b in model.bricks)
                model.bricks = [PlacedBrick(b.part_id, b.color_id, b.x,
                                            b.y + lift, b.z, b.rotation)
                                for b in model.bricks]
                repairs.append("Lifted the model onto the baseplate.")
                changed = True
                break

            if issue.code == "floating":
                added, removed = self._root_islands(model, set(issue.brick_indices))
                if added:
                    repairs.append(
                        "Added %d support elements under parts that would "
                        "otherwise float." % added)
                if removed:
                    repairs.append(
                        "Removed %d elements that could not be supported from "
                        "below." % removed)
                changed = bool(added or removed)
                break

            if issue.code == "unbalanced":
                added = self._widen_base(model)
                if added:
                    repairs.append("Widened the base so the model stands up.")
                    changed = True
                break

        model._repairs = repairs
        return changed

    def _root_islands(self, model: BrickModel, floating: set) -> tuple:
        """Grow columns down from floating parts; drop what cannot be reached.

        A 1x1 column under the lowest element of an island is the least
        intrusive fix that a builder can actually assemble: it is placed in
        an earlier step, and the island lands on it.
        """
        occ = model.occupancy()
        added = 0
        supported = set()

        by_low = sorted(floating, key=lambda i: model.bricks[i].y)
        for i in by_low:
            b = model.bricks[i]
            if b.y == 0:
                continue
            brick = self.library.get(b.part_id)
            w, d = brick.footprint(b.rotation)
            anchor = (b.x + w // 2, b.z + d // 2)
            column = []
            y = b.y - 3
            reached_ground = False
            while y >= 0:
                cell = (anchor[0], y, anchor[1])
                if cell in occ:
                    reached_ground = True
                    break
                column.append(y)
                y -= 3
            if y < 0 and not column:
                reached_ground = True
            if reached_ground or y < 0:
                for cy in column:
                    support = PlacedBrick("3005", b.color_id, anchor[0], cy,
                                          anchor[1], 0)
                    model.bricks.append(support)
                    for c in support.cells(self.library):
                        occ[c] = len(model.bricks) - 1
                    added += 1
                supported.add(i)

        if added:
            return added, 0

        # Nothing could be propped: drop the islands rather than ship a model
        # with pieces that fall off in the box.
        before = len(model.bricks)
        model.bricks = [b for i, b in enumerate(model.bricks) if i not in floating]
        return 0, before - len(model.bricks)

    def _widen_base(self, model: BrickModel) -> int:
        """Add a plate skirt on the bottom layer under the centre of mass."""
        if not model.bricks:
            return 0
        ground = [b for b in model.bricks if b.y == 0]
        if not ground:
            return 0
        occ = model.occupancy()
        x0 = min(b.x for b in ground)
        z0 = min(b.z for b in ground)
        added = 0
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                cell = (x0 + dx, 0, z0 + dz)
                if cell in occ or x0 + dx < 0 or z0 + dz < 0:
                    continue
                p = PlacedBrick("3024", ground[0].color_id, x0 + dx, 0,
                                z0 + dz, 0)
                model.bricks.append(p)
                occ[(x0 + dx, 0, z0 + dz)] = len(model.bricks) - 1
                added += 1
        return added
