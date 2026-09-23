"""Tests for separating the subject from its background.

Everything downstream is built on the cutout: the silhouette becomes the
model, so background that comes along becomes bricks, and subject that is
lost is missing from the box.  These check the cutout on the backgrounds
people actually photograph things against, and check that when the cutout
cannot be trusted we say so rather than quietly building a lump.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline import imaging

H, W = 300, 240


def subject() -> tuple:
    """A two-colour figure with arms and legs, centred in the frame."""
    rgb = np.zeros((H, W, 3), np.uint8)
    truth = np.zeros((H, W), dtype=bool)

    def box(y0, y1, x0, x1, colour):
        rgb[y0:y1, x0:x1] = colour
        truth[y0:y1, x0:x1] = True

    box(40, 90, 95, 145, (200, 60, 55))       # head
    box(90, 200, 80, 160, (45, 80, 190))      # body
    box(100, 160, 55, 80, (200, 60, 55))      # arms
    box(100, 160, 160, 185, (200, 60, 55))
    box(200, 250, 90, 115, (60, 60, 65))      # legs
    box(200, 250, 125, 150, (60, 60, 65))
    return rgb, truth


def on(background: np.ndarray) -> tuple:
    rgb, truth = subject()
    out = background.copy()
    out[truth] = rgb[truth]
    return out, truth


def plain() -> np.ndarray:
    return np.full((H, W, 3), 246, np.uint8)


def gradient() -> np.ndarray:
    ramp = np.linspace(215, 255, H).astype(np.uint8)
    return np.repeat(np.repeat(ramp[:, None], W, 1)[:, :, None], 3, 2)


def desk() -> np.ndarray:
    """Wood below, wall above: two backgrounds in one frame."""
    rng = np.random.default_rng(7)
    bg = np.zeros((H, W, 3), np.uint8)
    bg[:, :] = (165, 125, 85)
    grain = rng.normal(0, 9, (H, W)).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + grain[:, :, None], 0, 255).astype(np.uint8)
    bg[:70] = (150, 150, 155)
    return bg


def iou(mask: np.ndarray, truth: np.ndarray) -> float:
    return float((mask & truth).sum()) / float((mask | truth).sum())


# ---- the cutout itself ---------------------------------------------------

@pytest.mark.parametrize("name,background", [
    ("plain sweep", plain()),
    ("soft gradient", gradient()),
    ("desk against a wall", desk()),
])
def test_the_subject_is_found_on_an_ordinary_background(name, background):
    rgb, truth = on(background)
    cut = imaging.cut(rgb)
    assert iou(cut.mask, truth) > 0.95, name
    assert not cut.fallback, name


def test_a_thin_limb_survives_the_cutout():
    """The arms are the first thing a sloppy cutout loses."""
    rgb, truth = on(plain())
    mask = imaging.cut(rgb).mask
    left_arm = np.zeros_like(truth)
    left_arm[100:160, 55:80] = True
    assert (mask & left_arm).sum() / left_arm.sum() > 0.9


def test_a_subject_that_runs_off_the_frame_is_trimmed_at_the_edge():
    """A known trade-off, pinned here so nobody 'fixes' it by accident.

    The frame's edge is where the background is sampled from, so a subject
    that runs off the edge is partly sampled as background and loses that
    part.  The alternative -- trusting the edge -- loses the background of
    every ordinary photo instead, which is far worse.  What the customer is
    owed is a photo with the whole thing in it.
    """
    rgb, _ = on(plain())
    rgb[240:, 60:180] = (45, 80, 190)          # the legs continue past the photo
    mask = imaging.cut(rgb).mask
    assert not mask[-1].any()


def test_a_cutout_that_swallows_the_frame_falls_back():
    """A background the flood cannot reach leaves nearly everything 'subject'.

    That is a failed cutout, not an unusual photo, and it has to be caught:
    the fallback is worse than a good flood but much better than a frame,
    and it sets the flag that warns the customer.
    """
    rgb, truth = on(plain())
    # Four unrelated colours round the edge: the background sample is spread
    # so thin that the flood has nothing to follow.
    rgb[:, 0:12] = (30, 140, 60)
    rgb[:, 228:] = (200, 170, 40)
    rgb[0:10, :] = (120, 40, 160)
    rgb[290:, :] = (20, 60, 200)
    cut = imaging.cut(rgb)
    assert cut.fallback
    assert cut.mask.mean() <= imaging.MAX_SUBJECT
    assert iou(cut.mask, truth) > iou(np.ones_like(truth), truth)


def test_the_flood_keeps_background_that_is_walled_off():
    """Background enclosed by the subject is background, but unreachable.

    The flood works inward from the frame, so a hole in the middle of the
    subject is never reached and stays part of it.  That is the intended
    trade: it keeps a dark eye from punching through a face.
    """
    rgb, _ = on(plain())
    rgb[120:140, 105:135] = 246                # a window of background in the body
    mask = imaging.cut(rgb).mask
    assert mask[125:135, 110:130].all()


# ---- labelling, which the cutout is built on ------------------------------

def test_components_are_four_connected():
    m = np.zeros((10, 10), dtype=bool)
    m[2, 2] = m[3, 3] = True                   # touching only at a corner
    _labels, sizes = imaging._label(m)
    assert len(sizes) == 2


def test_labelling_separates_regions_and_counts_them():
    m = np.zeros((40, 40), dtype=bool)
    m[2:8, 2:8] = True
    m[2:8, 20:30] = True
    m[20:38, 5:35] = True
    labels, sizes = imaging._label(m)
    assert len(sizes) == 3
    assert sum(sizes.values()) == int(m.sum())
    assert labels[3, 3] != labels[3, 22]
    assert (imaging._largest_component(m) == (labels == max(sizes, key=sizes.get))).all()


def test_a_hole_is_not_part_of_the_shape_around_it():
    m = np.zeros((20, 20), dtype=bool)
    m[4:16, 4:16] = True
    m[8:12, 8:12] = False
    labels, sizes = imaging._label(m)
    assert len(sizes) == 1
    assert labels[10, 10] == 0


def test_the_flood_reaches_the_border_and_nothing_else():
    passable = np.zeros((20, 20), dtype=bool)
    passable[0:20, 0:3] = True                 # a strip along the left edge
    passable[8:12, 8:12] = True                # an island in the middle
    reached = imaging._flood_from_border(passable)
    assert reached[:, 0:3].all()
    assert not reached[8:12, 8:12].any()
