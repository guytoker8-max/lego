"""The pipeline: one stage after another, each a separate service.

    reference photos
      -> ReferenceAnalyzer     what is this, and what could we not tell
      -> GeometryReconstructor a filled volume on the stud grid
      -> BrickOptimizer        hollow it, calm the colours
      -> BrickGenerator        real elements, real colours, real positions
      -> StructuralValidator   prove it stands; repair it until it does
      -> InstructionGenerator  a booklet that can actually be followed
      -> PartsInventory        the bill of materials, counted from the model
      -> PricingEngine         a price traced to that bill
      -> OrderService          (on request) the physical kit

No stage reaches past its neighbours, and no stage is a prompt.  The vision
model names the subject and judges its depth; everything after that is
geometry and arithmetic, which is what makes the result the same every time
and the parts list something you can put in a box.
"""

from __future__ import annotations

import logging

from ..config import (DETAIL_MODIFIERS, PRESETS_BY_KEY, PRIORITY_MODIFIERS,
                      DEFAULT_PRESET, SizePreset)
from ..library import DEFAULT_COLORS, LIBRARY
from ..models import Analysis, BrickModel
from .brick_generator import BrickGenerator
from .geometry import GeometryReconstructor, EmptySilhouetteError
from .instructions import InstructionGenerator, difficulty, estimate_build_time
from .inventory import PartsInventory
from .optimizer import BrickOptimizer
from .pricing import PricingEngine
from .reference_analyzer import ReferenceAnalyzer, NoUsableReferenceError
from .validator import StructuralValidator

log = logging.getLogger(__name__)

# The four things the app says it is doing, in the brief's own words.
STAGES = (
    ("analyzing", "Analysing your model..."),
    ("planning", "Planning the build..."),
    ("bricks", "Choosing bricks..."),
    ("instructions", "Creating instructions..."),
)


class BuildPipeline:
    def __init__(self, api_key: str | None = None, library=LIBRARY):
        self.library = library
        self.analyzer = ReferenceAnalyzer(api_key=api_key)
        self.geometry = GeometryReconstructor()
        self.optimizer = BrickOptimizer()
        self.validator = StructuralValidator(library)
        self.instructions = InstructionGenerator(library)
        self.inventory = PartsInventory(library)
        self.pricing = PricingEngine()

    # ---- the two halves --------------------------------------------------

    def analyze(self, paths: list, angles: list | None = None) -> tuple:
        """First half: look at the photos and work out what to ask."""
        return self.analyzer.analyze(paths, angles)

    def build(self, views: list, analysis: Analysis, answers: dict,
              progress=None) -> dict:
        """Second half: everything from the answers to a priced, valid set."""
        emit = progress or (lambda *a, **k: None)

        preset = PRESETS_BY_KEY.get(answers.get("size", DEFAULT_PRESET),
                                    PRESETS_BY_KEY[DEFAULT_PRESET])
        detail = DETAIL_MODIFIERS.get(answers.get("detail", "balanced"),
                                      DETAIL_MODIFIERS["balanced"])
        priority = PRIORITY_MODIFIERS.get(answers.get("priority", "balanced"),
                                          PRIORITY_MODIFIERS["balanced"])
        interpret = answers.get("unseen_back", "yes") != "no"
        budget = int(preset.max_pieces * detail["pieces"])

        emit("planning", "Planning the build...", 0.30)
        emit("bricks", "Choosing bricks...", 0.50)
        volume, width, bricks, palette = self._fit_to_budget(
            views, analysis, preset, budget, interpret, priority, detail)

        model = BrickModel(
            name=analysis.display_name or "Your Model",
            subject=analysis.subject,
            bricks=bricks,
            size_studs=(volume.shape[0], volume.shape[1] * 3, volume.shape[2]),
            source={
                "analysis": analysis.to_dict(),
                "answers": answers,
                "preset": preset.to_dict(),
                "width_studs": width,
                "palette": palette.as_dicts(),
            },
            library=self.library,
        )

        emit("validating", "Checking it can be built...", 0.70)
        report = self.validator.validate_and_repair(model)
        if not report.ok:
            raise UnbuildableError(
                "This model could not be made buildable automatically.",
                report.to_dict())

        emit("instructions", "Creating instructions...", 0.85)
        self.instructions.generate(model)
        step_problems = self.instructions.verify(model)
        if step_problems:
            # The booklet, not the model, is wrong: rebuild the ordering once
            # with every element forced to wait for its support.
            log.warning("instruction order needed a second pass: %s",
                        step_problems[:3])
            self.instructions.generate(model)
            step_problems = self.instructions.verify(model)

        lines = self.inventory.bill_of_materials(model)
        mismatch = self.inventory.reconcile(model, lines)
        if mismatch:
            raise InconsistentModelError(
                "The parts list does not match the model.", mismatch)

        emit("done", "Your set is ready.", 1.0)
        return self.package(model, lines, step_problems)

    # ---- packaging -------------------------------------------------------

    def package(self, model: BrickModel, lines=None,
                step_problems: list | None = None) -> dict:
        lines = lines if lines is not None else \
            self.inventory.bill_of_materials(model)
        price = self.pricing.price(lines, model.weight_g)
        time_est = estimate_build_time(model)
        return {
            "model": model.to_dict(),
            "summary": {
                "name": model.name,
                "subject": model.subject,
                "piece_count": model.piece_count,
                "color_count": len(model.color_ids),
                "dimensions_cm": list(model.dimensions_cm),
                "weight_g": model.weight_g,
                "build_time": time_est,
                "difficulty": difficulty(model),
                "step_count": len(model.steps),
                "fingerprint": model.fingerprint(),
            },
            "parts": self.inventory.summary(model),
            "steps": self.instructions.describe(model),
            "price": price,
            "validation": model.validation,
            "warnings": (step_problems or []) +
                        list(model.source.get("analysis", {}).get("warnings", [])),
        }

    # ---- sizing ----------------------------------------------------------

    def _fit_to_budget(self, views, analysis, preset: SizePreset, budget: int,
                       interpret: bool, priority: dict, detail: dict):
        """Pick the stud width that lands inside the preset's piece budget.

        The count is *measured*, by actually laying the bricks, not predicted
        from the cell count: how many elements a shape needs depends on how
        its colours fall, and a guess is wrong by enough to matter. Laying a
        layer is cheap, so a trial build and one correction is affordable,
        and it is what makes "Small" mean something. Piece count grows with
        roughly the cube of the width, which is how the correction is sized.
        """
        # "Fewer pieces" has to mean a visibly simpler model, not just a cap
        # the build never reaches. Studs are 8 mm whatever we do, so the only
        # way to carry less detail is to use fewer of them -- which also makes
        # the model smaller. That is the honest trade, and it is the one the
        # question asked about.
        width = int(round(self._width_for_dimension(views[0], preset)
                          * detail["pieces"] ** (1.0 / 2.6)))
        width = max(8, width)
        best = None
        for attempt in range(4):
            volume = self.geometry.reconstruct(
                views, analysis, width_studs=width, interpret_unseen=interpret)
            volume = self.optimizer.hollow(volume, shell=priority["shell"],
                                           lattice=priority["lattice"],
                                           keep_solid=priority["solid"])
            volume, bricks, palette = self._lay_and_ground(
                volume, preset, detail, priority)
            # Count after repair, not before. Propping an overhang adds real
            # pieces to the box, and a budget that ignores them is a budget
            # the finished set quietly breaks.
            bricks = self._repaired(bricks, volume)
            count = len(bricks)
            # Keep the largest candidate that fits the budget; if none fits,
            # keep the smallest we saw, so the preset is never blown through.
            if best is None or _better(count, len(best[2]), budget):
                best = (volume, width, bricks, palette)
            if count <= budget or width <= 8:
                break
            scale = (budget / float(count)) ** (1.0 / 2.6)
            new_width = max(8, int(width * scale))
            width = new_width if new_width < width else width - 2
        return best

    def _lay_and_ground(self, volume, preset, detail: dict, priority: dict,
                        rounds: int = 8):
        """Tile, prop whatever came out hanging, and tile again.

        Two or three passes settle it: filling under a hanging brick puts
        cells where the next tiling can use them, and each pass leaves less
        hanging than the last.
        """
        bricks, palette = self._lay_bricks(volume, preset, detail, priority)
        # ``ground_bricks`` supersedes the cell-level pass: it knows the
        # footprints, so it props what actually hangs and nothing else.
        # Running both double-props, and every extra cell is extra pieces.
        for _ in range(rounds):
            volume, filled = self.optimizer.ground_bricks(
                volume, bricks, self.library)
            if not filled:
                break
            bricks, palette = self._lay_bricks(volume, preset, detail, priority)
        return volume, bricks, palette

    def _repaired(self, bricks: list, volume) -> list:
        """Run the validator's repair now, so its pieces are counted too."""
        probe = BrickModel(name="probe", bricks=list(bricks),
                           size_studs=(volume.shape[0], volume.shape[1] * 3,
                                       volume.shape[2]),
                           library=self.library)
        self.validator.validate_and_repair(probe)
        return probe.bricks

    def _lay_bricks(self, volume, preset: SizePreset, detail: dict,
                    priority: dict):
        """Colours chosen and elements placed, for one candidate volume."""
        n_colors = max(3, int(round(preset.colors * detail["colors"])))
        palette = DEFAULT_COLORS.reduce_to(volume.rgb[volume.solid], n_colors)
        generator = BrickGenerator(self.library, palette,
                                   stagger=priority["stagger"])
        cids = generator._match_colors(volume)
        cids = self.optimizer.despeckle(cids, volume.solid,
                                        threshold=detail["despeckle"])
        cids = self.optimizer.merge_short_runs(cids, volume.solid,
                                               threshold=detail["despeckle"] + 1.5)
        return self._tile(generator, volume, cids), palette

    def _width_for_dimension(self, view, preset: SizePreset) -> int:
        """Cap the width so the model also fits the preset's centimetres."""
        from ..library import STUD_MM
        by_mm = int(preset.max_dimension_cm * 10 / STUD_MM)
        aspect = view.aspect
        if aspect < 1.0:                      # taller than wide: height binds
            by_mm = int(by_mm * aspect * 1.2)
        return max(8, min(preset.width_studs, by_mm))

    @staticmethod
    def _tile(generator: BrickGenerator, volume, cids) -> list:
        from ..models import PlacedBrick
        bricks = []
        seams = set()
        for y in range(volume.shape[1]):
            layer = volume.solid[:, y, :]
            if not layer.any():
                seams = set()
                continue
            support = volume.solid[:, y - 1, :] if y > 0 else None
            placements, seams = generator._tile_layer(layer, cids[:, y, :],
                                                      seams, support)
            for part_id, cid, x, z, rot in placements:
                bricks.append(PlacedBrick(part_id, int(cid), x, y * 3, z, rot))
        return bricks


def _better(count: int, incumbent: int, budget: int) -> bool:
    """Is a candidate of this size a better fit for the budget?"""
    fits, had = count <= budget, incumbent <= budget
    if fits and had:
        return count > incumbent        # use the budget, don't waste it
    if fits != had:
        return fits                     # fitting always beats not fitting
    return count < incumbent            # neither fits: take the smaller


class UnbuildableError(RuntimeError):
    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


class InconsistentModelError(RuntimeError):
    def __init__(self, message: str, details: list):
        super().__init__(message)
        self.details = details
