"""Stage 2 - GeometryReconstructor.

Turns reference photos into a filled 3D volume on the stud grid, plus a
colour for every filled cell.  Everything after this stage works on the
volume, not on the photo.

How the third dimension comes about
-----------------------------------
Two photos or more (front and side) give it honestly: a cell is solid only
if it is inside the subject in *every* view that can see it.  That is a
visual hull, and it is the same carving a turntable scanner does, just with
two silhouettes instead of two hundred.

One photo cannot give it honestly, so we say so.  The silhouette is extruded
with a depth profile -- how far a point bulges toward the viewer depends on
how far it sits from the outline, which is what makes a face read as a face
instead of a cardboard cut-out.  The analysis stage picks the profile and
the depth, and the user is asked before we do it at all.

Coordinates match the brick library: x and z are studs, y counts *layers*
here (one brick, three plate units) and is converted on the way out.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..library import STUD_MM, PLATE_MM
from ..models import Analysis
from . import imaging
from .reference_analyzer import View

BRICK_MM = 3 * PLATE_MM          # a brick layer is 9.6 mm tall


@dataclass
class Volume:
    """A filled shape on the stud grid, with a colour per cell."""

    solid: np.ndarray        # bool  (X, Y, Z)
    rgb: np.ndarray          # uint8 (X, Y, Z, 3)
    layer_plates: int = 3    # plate units per y layer

    @property
    def shape(self) -> tuple:
        return self.solid.shape

    @property
    def filled(self) -> int:
        return int(self.solid.sum())

    def size_mm(self) -> tuple:
        x, y, z = self.solid.shape
        return (x * STUD_MM, y * self.layer_plates * PLATE_MM, z * STUD_MM)

    def surface(self) -> np.ndarray:
        """Cells with at least one face exposed, inside cavities included."""
        s = self.solid
        inner = np.ones_like(s)
        inner[1:, :, :] &= s[:-1, :, :]
        inner[:-1, :, :] &= s[1:, :, :]
        inner[:, 1:, :] &= s[:, :-1, :]
        inner[:, :-1, :] &= s[:, 1:, :]
        inner[:, :, 1:] &= s[:, :, :-1]
        inner[:, :, :-1] &= s[:, :, 1:]
        return s & ~inner

    def visible(self) -> np.ndarray:
        """Cells someone can actually see from outside the finished model.

        Not the same as ``surface``. Hollowing leaves internal walls whose
        faces are exposed to a sealed cavity: exposed, but seen by nobody.
        The distinction is worth drawing because a cell nobody sees can be
        any colour, and making the whole inside one colour is what lets those
        walls tile into long bricks instead of a thousand 1x1s.

        Found by flooding air inward from outside the model and keeping the
        solid cells that air touches.
        """
        s = self.solid
        air = ~s
        # Pad by one so the flood always has an outside to start from.
        padded = np.pad(air, 1, constant_values=True)
        reached = np.zeros_like(padded)
        reached[0, :, :] = reached[-1, :, :] = True
        reached[:, 0, :] = reached[:, -1, :] = True
        reached[:, :, 0] = reached[:, :, -1] = True
        reached &= padded
        while True:
            grown = reached.copy()
            grown[1:, :, :] |= reached[:-1, :, :]
            grown[:-1, :, :] |= reached[1:, :, :]
            grown[:, 1:, :] |= reached[:, :-1, :]
            grown[:, :-1, :] |= reached[:, 1:, :]
            grown[:, :, 1:] |= reached[:, :, :-1]
            grown[:, :, :-1] |= reached[:, :, 1:]
            grown &= padded
            if grown.sum() == reached.sum():
                break
            reached = grown
        outside = reached[1:-1, 1:-1, 1:-1]

        touching = np.zeros_like(s)
        touching[1:, :, :] |= outside[:-1, :, :]
        touching[:-1, :, :] |= outside[1:, :, :]
        touching[:, 1:, :] |= outside[:, :-1, :]
        touching[:, :-1, :] |= outside[:, 1:, :]
        touching[:, :, 1:] |= outside[:, :, :-1]
        touching[:, :, :-1] |= outside[:, :, 1:]
        return s & touching


class GeometryReconstructor:
    def __init__(self, min_depth: int = 1):
        self.min_depth = min_depth

    def reconstruct(self, views: list, analysis: Analysis, *,
                    width_studs: int, interpret_unseen: bool = True) -> Volume:
        front = views[0]
        side = self._find(views, ("side", "left", "right"))

        w, h = self._grid_size(front, width_studs)
        mask = imaging.resize_mask(front.mask, w, h)
        rgb = imaging.resize_rgb(front.rgb, w, h)

        if analysis.symmetry == "left-right":
            mask = self._enforce_symmetry(mask)

        mask = self._drop_specks(mask)
        if not mask.any():                       # nothing survived the shrink
            raise EmptySilhouetteError(
                "The subject came out empty at this size. A larger size or a "
                "photo with more contrast against the background would help.")

        if side is not None:
            solid = self._visual_hull(mask, side, h)
        elif interpret_unseen:
            solid = self._extrude(mask, analysis)
        else:
            solid = self._extrude_flat(mask)

        colors = self._colorise(solid, rgb, side)
        return Volume(solid=solid, rgb=colors)

    # ---- sizing ----------------------------------------------------------

    def _grid_size(self, view: View, width_studs: int) -> tuple:
        """Stud grid that keeps the subject's real proportions.

        A brick layer is 9.6 mm tall against an 8 mm stud pitch, so a square
        subject needs fewer layers than columns or it comes out stretched.
        """
        mh, mw = view.mask.shape
        aspect = mw / mh if mh else 1.0
        layers = int(round((width_studs / aspect) * STUD_MM / BRICK_MM))
        return width_studs, max(2, layers)

    # ---- depth -----------------------------------------------------------

    def _visual_hull(self, front: np.ndarray, side: View, layers: int) -> np.ndarray:
        """Carve with two silhouettes: solid only where both agree.

        The two photos share a height, so the side view is resampled to the
        same number of layers and its width becomes the model's depth.
        """
        h, w = front.shape
        depth = self._side_width(side, w, layers)
        side_mask = imaging.resize_mask(side.mask, depth, layers)

        f = np.flipud(front).T                       # (X, Y), y up from base
        s = np.flipud(side_mask).T                   # (Z, Y)
        return f[:, :, None] & s.T[None, :, :]       # (X, Y, Z)

    @staticmethod
    def _find(views: list, angles: tuple) -> View | None:
        """The first reference shot from one of these angles, if we got one."""
        for v in views[1:]:
            if v.angle in angles:
                return v
        return None

    def _side_width(self, side: View, front_w: int, layers: int) -> int:
        """Depth in studs implied by the side photo, at the model's height."""
        mh, mw = side.mask.shape
        aspect = mw / mh if mh else 1.0
        depth = int(round(layers * BRICK_MM / STUD_MM * aspect))
        return max(self.min_depth, min(depth, front_w * 3))

    def _extrude(self, mask: np.ndarray, analysis: Analysis) -> np.ndarray:
        """Give a single silhouette a believable thickness.

        Depth at a point follows its distance from the outline, so the middle
        of a form stands proud and the rim tapers.  The exponent is what
        separates a ball from a shoebox.
        """
        h, w = mask.shape
        depth = max(self.min_depth,
                    int(round(w * float(analysis.depth_ratio))))
        dist = imaging.distance_inside(mask)
        peak = dist.max() or 1.0
        t = np.clip(dist / peak, 0.0, 1.0)

        exponent = {"flat": 0.0, "boxy": 0.12, "rounded": 0.5, "deep": 0.35}
        e = exponent.get(analysis.depth_profile, 0.5)
        profile = np.ones_like(t) if e == 0.0 else np.power(t, e)

        # Quantise the thickness into whole cells.  A continuous profile gives
        # every column its own depth, which in plan view is a field of
        # one-cell fringes -- and a one-cell fringe is bought as 1x1 bricks.
        # Rounding to whole cells merges neighbouring columns into bands that
        # tile into long bricks, and at 8 mm a cell the shape is unchanged.
        half = np.round(profile * depth / 2.0)
        half = np.where(mask, np.maximum(half, 1.0), 0.0)

        centre = depth / 2.0
        zz = np.arange(depth, dtype=np.float32) + 0.5
        # (rows, cols, depth) -> keep cells within the half-thickness
        slab = np.abs(zz[None, None, :] - centre) <= half[:, :, None]
        slab &= mask[:, :, None]

        solid = np.flipud(slab).transpose(1, 0, 2)    # (X, Y, Z), y up
        return solid

    def _extrude_flat(self, mask: np.ndarray, depth: int = 2) -> np.ndarray:
        """No interpretation of the unseen side: a relief panel, honestly thin."""
        slab = np.repeat(mask[:, :, None], depth, axis=2)
        return np.flipud(slab).transpose(1, 0, 2)

    # ---- colour ----------------------------------------------------------

    def _colorise(self, solid: np.ndarray, rgb: np.ndarray,
                  side: View | None) -> np.ndarray:
        """Paint the volume from the photo.

        Every cell in a column takes the front photo's colour for that column,
        so the front face is right and the inside -- which nobody ever sees --
        matches rather than going grey.
        """
        front_rgb = np.flipud(rgb).transpose(1, 0, 2)          # (X, Y, 3)
        out = np.broadcast_to(front_rgb[:, :, None, :],
                              solid.shape + (3,)).copy()
        out[~solid] = 0
        return out.astype(np.uint8)

    # ---- tidying ---------------------------------------------------------

    def _enforce_symmetry(self, mask: np.ndarray) -> np.ndarray:
        """Union the silhouette with its mirror: fixes a limb lost to shadow."""
        return mask | mask[:, ::-1]

    def _drop_specks(self, mask: np.ndarray, min_cells: int = 3) -> np.ndarray:
        """Remove stray single studs left by shrinking a busy photo."""
        labels, sizes = imaging._label(mask)
        keep = {k for k, v in sizes.items() if v >= min_cells}
        if not keep:
            return mask
        return np.isin(labels, list(keep))


class EmptySilhouetteError(ValueError):
    """The subject vanished when reduced to the stud grid."""
