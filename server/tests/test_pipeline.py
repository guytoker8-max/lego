"""Tests for the things that would be expensive to get wrong.

Weighted toward the promise rather than the plumbing: that a model is
buildable, that the parts list matches it, and that bad input fails in a way
a person can act on rather than a way that ships a broken box.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.library import LIBRARY, DEFAULT_COLORS, UnknownPartError
from app.models import BrickModel, PlacedBrick
from app.pipeline.geometry import EmptySilhouetteError
from app.pipeline.instructions import InstructionGenerator
from app.pipeline.inventory import PartsInventory
from app.pipeline.pricing import PricingEngine
from app.pipeline.reference_analyzer import NoUsableReferenceError
from app.pipeline.runner import BuildPipeline
from app.pipeline.validator import StructuralValidator

SAMPLES = "/mnt/project-files/legoize/samples"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pipeline():
    return BuildPipeline(api_key=None)


@pytest.fixture(scope="session")
def built(pipeline):
    analysis, views = pipeline.analyze(["%s/emblem.png" % SAMPLES])
    return pipeline.build(views, analysis,
                          {"size": "small", "detail": "balanced",
                           "priority": "balanced"})


def _write(tmp_path, name, array):
    path = tmp_path / name
    Image.fromarray(array.astype(np.uint8)).save(path)
    return str(path)


# ---------------------------------------------------------------------------
# the brick library is the only source of parts
# ---------------------------------------------------------------------------

def test_library_refuses_unknown_parts():
    with pytest.raises(UnknownPartError):
        LIBRARY.get("not-a-part")


def test_every_catalog_part_has_real_dimensions():
    for brick in LIBRARY.all():
        w, h, d = brick.size_mm()
        assert w > 0 and h > 0 and d > 0
        assert brick.weight_g > 0
        assert brick.base_cost > 0


def test_generated_models_only_use_catalogued_parts(built):
    for b in built["model"]["bricks"]:
        assert LIBRARY.exists(b["part_id"])


def test_generated_models_only_use_real_colors(built):
    from app.vendor.legoize import palette
    for b in built["model"]["bricks"]:
        assert b["color_id"] in palette.BY_ID


# ---------------------------------------------------------------------------
# the model is buildable
# ---------------------------------------------------------------------------

def test_built_model_passes_validation(built):
    assert built["validation"]["ok"] is True
    assert built["validation"]["stats"]["floating"] == 0


def test_no_two_bricks_share_a_cell(built):
    model = BrickModel.from_dict(built["model"])
    cells = set()
    for b in model.bricks:
        for c in b.cells(LIBRARY):
            assert c not in cells, "two elements occupy %s" % (c,)
            cells.add(c)


def test_nothing_sits_below_the_baseplate(built):
    assert all(b["y"] >= 0 for b in built["model"]["bricks"])


def test_validator_catches_a_floating_brick():
    model = BrickModel(name="t", bricks=[
        PlacedBrick("3001", 4, 0, 0, 0),
        PlacedBrick("3001", 4, 0, 9, 0),        # two layers of air below it
    ])
    report = StructuralValidator().validate(model)
    assert not report.ok
    assert any(i.code == "floating" for i in report.issues)


def test_validator_repairs_a_floating_brick():
    model = BrickModel(name="t", bricks=[
        PlacedBrick("3001", 4, 0, 0, 0),
        PlacedBrick("3001", 4, 0, 9, 0),
    ])
    report = StructuralValidator().validate_and_repair(model)
    assert report.ok
    assert report.repairs, "a repair happened but was not reported"


def test_validator_catches_overlapping_bricks():
    model = BrickModel(name="t", bricks=[
        PlacedBrick("3001", 4, 0, 0, 0),
        PlacedBrick("3001", 4, 1, 0, 0),
    ])
    report = StructuralValidator().validate(model)
    assert any(i.code == "overlap" for i in report.issues)


def test_a_brick_held_only_from_above_is_not_treated_as_supported():
    """It is connected once finished, but there is no step that places it."""
    model = BrickModel(name="t", bricks=[
        PlacedBrick("3001", 4, 0, 0, 0),
        PlacedBrick("3005", 4, 0, 3, 0),      # rests on the first
        PlacedBrick("3005", 4, 5, 3, 0),      # hangs off nothing at all
    ])
    report = StructuralValidator().validate(model)
    assert any(i.code == "floating" for i in report.issues)


# ---------------------------------------------------------------------------
# the digital model, the parts list and the booklet are the same object
# ---------------------------------------------------------------------------

def test_parts_list_matches_the_model_exactly(built):
    model = BrickModel.from_dict(built["model"])
    inventory = PartsInventory()
    lines = inventory.bill_of_materials(model)
    assert inventory.reconcile(model, lines) == []
    assert sum(l.quantity for l in lines) == model.piece_count


def test_instructions_place_every_brick_exactly_once(built):
    model = BrickModel.from_dict(built["model"])
    placed = [i for s in model.steps for i in s.brick_indices]
    assert sorted(placed) == list(range(len(model.bricks)))


def test_every_step_can_be_built_on_the_one_before(built):
    model = BrickModel.from_dict(built["model"])
    assert InstructionGenerator().verify(model) == []


def test_one_fingerprint_across_model_parts_and_steps(built):
    assert built["model"]["fingerprint"] == built["parts"]["fingerprint"]
    assert built["summary"]["fingerprint"] == built["parts"]["fingerprint"]


def test_fingerprint_changes_when_the_model_does(built):
    model = BrickModel.from_dict(built["model"])
    before = model.fingerprint()
    model.bricks.append(PlacedBrick("3005", 4, 0, 0, 0))
    assert model.fingerprint() != before


# ---------------------------------------------------------------------------
# size presets mean something
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size,cap", [("mini", 180), ("small", 400)])
def test_presets_respect_their_piece_budget(pipeline, size, cap):
    analysis, views = pipeline.analyze(["%s/emblem.png" % SAMPLES])
    out = pipeline.build(views, analysis,
                         {"size": size, "detail": "balanced",
                          "priority": "balanced"})
    assert out["summary"]["piece_count"] <= cap


def test_bigger_presets_give_bigger_models(pipeline):
    analysis, views = pipeline.analyze(["%s/emblem.png" % SAMPLES])
    counts = [
        pipeline.build(views, analysis,
                       {"size": s, "detail": "balanced", "priority": "balanced"}
                       )["summary"]["piece_count"]
        for s in ("mini", "small", "medium")
    ]
    assert counts == sorted(counts)


# ---------------------------------------------------------------------------
# pricing traces to the parts
# ---------------------------------------------------------------------------

def test_price_is_derived_from_the_bill_of_materials(built):
    model = BrickModel.from_dict(built["model"])
    lines = PartsInventory().bill_of_materials(model)
    price = PricingEngine().price(lines, model.weight_g)
    parts_cost = price["breakdown"]["parts"]
    assert parts_cost > 0
    # Doubling the model must cost more in bricks.
    doubled = PricingEngine().price(lines + lines, model.weight_g * 2)
    assert doubled["breakdown"]["parts"] > parts_cost


def test_price_breakdown_adds_up(built):
    model = BrickModel.from_dict(built["model"])
    lines = PartsInventory().bill_of_materials(model)
    p = PricingEngine().price(lines, model.weight_g)
    b = p["breakdown"]
    assert round(b["subtotal"] + b["vat"] + b["shipping"], 2) == p["total"]
    assert round(b["parts"] + b["packaging"] + b["handling"] + b["margin"], 2) \
        == pytest.approx(b["subtotal"], abs=0.02)


# ---------------------------------------------------------------------------
# bad input fails in a way a person can act on
# ---------------------------------------------------------------------------

def test_a_file_that_is_not_an_image_is_rejected(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("this is not a photo")
    with pytest.raises(NoUsableReferenceError):
        BuildPipeline(api_key=None).analyze([str(bad)])


def test_a_blank_photo_is_reported_not_crashed(tmp_path, pipeline):
    blank = _write(tmp_path, "blank.png", np.full((300, 300, 3), 255))
    analysis, views = pipeline.analyze([blank])
    # Nothing to find: either it warns, or the build refuses cleanly.
    try:
        pipeline.build(views, analysis, {"size": "small"})
    except EmptySilhouetteError as exc:
        assert "size" in str(exc) or "contrast" in str(exc)


def test_a_blurry_photo_is_flagged(tmp_path, pipeline):
    rng = np.random.default_rng(1)
    base = np.full((300, 300, 3), 240, dtype=np.uint8)
    base[90:210, 90:210] = 60
    blurred = Image.fromarray(base).filter(
        __import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(9))
    path = tmp_path / "blurry.png"
    blurred.save(path)
    analysis, _ = pipeline.analyze([str(path)])
    assert any("soft" in w or "detail" in w for w in analysis.warnings)


def test_multiple_objects_are_flagged(tmp_path, pipeline):
    img = np.full((300, 300, 3), 245, dtype=np.uint8)
    img[60:140, 40:120] = (200, 40, 30)
    img[160:240, 180:260] = (30, 90, 200)
    analysis, _ = pipeline.analyze([_write(tmp_path, "two.png", img)])
    assert any("more than one" in w for w in analysis.warnings)


def test_a_tiny_subject_still_produces_a_buildable_model(tmp_path, pipeline):
    img = np.full((400, 400, 3), 248, dtype=np.uint8)
    img[190:215, 190:215] = (200, 40, 30)
    analysis, views = pipeline.analyze([_write(tmp_path, "tiny.png", img)])
    try:
        out = pipeline.build(views, analysis, {"size": "mini"})
    except EmptySilhouetteError:
        return                     # refusing is a valid outcome here
    assert out["validation"]["ok"]


def test_a_very_busy_photo_still_finishes(pipeline):
    analysis, views = pipeline.analyze(["%s/sunset.png" % SAMPLES])
    out = pipeline.build(views, analysis, {"size": "medium"})
    assert out["validation"]["ok"]
    assert out["summary"]["piece_count"] > 0


def test_missing_inventory_blocks_the_order():
    """A part the library cannot supply must not reach a customer."""
    from app.library import BrickLibrary
    from app.library.bricks import CATALOG
    scarce = BrickLibrary(CATALOG, availability={"3005": 2})
    inventory = PartsInventory(scarce)
    model = BrickModel(name="t", library=scarce,
                       bricks=[PlacedBrick("3005", 4, i, 0, 0) for i in range(8)])
    lines = inventory.bill_of_materials(model)
    assert inventory.check_availability(lines)
