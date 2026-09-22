"""Stage 3 - BrickGenerator.

Turns the filled volume into actual elements: a part id, a real colour, a
position and an orientation for each one.  After this stage the model is a
list of things you could pick out of a box, not a shape.

Every element comes from the brick library.  Nothing here may invent a size.

Two things make this more than a tiler:

*Colour first.*  A brick is one colour, so a region is tiled only within a
single matched colour.  Matching happens against the real moulded palette
before tiling, never after, or the parts list would name colours that are
not made.

*Seams are staggered.*  Two layers whose joints line up make a wall that
splits along that line -- the single most common way a brick model falls
apart in the hand.  Candidate placements are scored against the joints in
the layer below, so courses overlap like brickwork.
"""

from __future__ import annotations

import numpy as np

from ..library import LIBRARY, BrickLibrary, DEFAULT_COLORS, ColorLibrary
from ..models import PlacedBrick
from .geometry import Volume

SEAM_PENALTY = 2.2       # studs of area a shared joint is worth giving up
UNSUPPORTED_PENALTY = 6.0  # studs worth giving up to land on something solid


class BrickGenerator:
    def __init__(self, library: BrickLibrary = LIBRARY,
                 colors: ColorLibrary = DEFAULT_COLORS,
                 max_length: int = 8, max_width: int = 2,
                 stagger: bool = True):
        self.library = library
        self.colors = colors
        self.catalog = library.building_set(max_length=max_length,
                                            max_width=max_width, kinds=("brick",))
        self.stagger = stagger

    def generate(self, volume: Volume) -> list:
        """Volume -> [PlacedBrick], bottom layer first."""
        color_idx = self._match_colors(volume)
        X, Y, Z = volume.shape
        bricks = []
        seams_below: set = set()

        for y in range(Y):
            layer = volume.solid[:, y, :]
            if not layer.any():
                seams_below = set()
                continue
            support = volume.solid[:, y - 1, :] if y > 0 else None
            placements, seams = self._tile_layer(
                layer, color_idx[:, y, :], seams_below, support)
            y_plates = y * 3
            for part_id, cid, x, z, rot in placements:
                bricks.append(PlacedBrick(part_id, cid, x, y_plates, z, rot))
            seams_below = seams if self.stagger else set()
        return bricks

    # ---- colour ----------------------------------------------------------

    def _match_colors(self, volume: Volume) -> np.ndarray:
        """Nearest real brick colour id for every filled cell, -1 elsewhere."""
        flat = volume.rgb.reshape(-1, 3)
        idx = self.colors.match(flat)
        ids = self.colors.ids_for(idx).reshape(volume.shape)
        ids = np.where(volume.solid, ids, -1)
        return ids

    # ---- tiling ----------------------------------------------------------

    def _tile_layer(self, layer: np.ndarray, cids: np.ndarray,
                    seams_below: set, support: np.ndarray | None = None) -> tuple:
        """Cover one layer with the largest single-colour bricks that fit.

        ``support`` is the layer below, if there is one.  A brick that lands
        entirely over empty space has to be propped later with a column of
        1x1s, so a placement that catches even a corner of the layer below is
        worth several studs of area -- which is what the penalty buys.
        """
        X, Z = layer.shape
        free = layer.copy()
        placements = []
        seams = set()

        for z in range(Z):
            for x in range(X):
                if not free[x, z]:
                    continue
                cid = int(cids[x, z])
                best = self._best_brick(free, cids, x, z, cid, seams_below,
                                        support)
                part_id, rot, w, d = best
                free[x:x + w, z:z + d] = False
                placements.append((part_id, cid, x, z, rot))
                for dz in range(d):
                    seams.add((x, z + dz))
                    seams.add((x + w, z + dz))
        return placements, seams

    def _best_brick(self, free: np.ndarray, cids: np.ndarray,
                    x: int, z: int, cid: int, seams_below: set,
                    support: np.ndarray | None = None) -> tuple:
        """Largest brick that fits here in this colour, joints permitting."""
        X, Z = free.shape
        best = None
        best_score = -1e9
        for brick in self.catalog:
            for rot in brick.rotations():
                w, d = brick.footprint(rot)
                if x + w > X or z + d > Z:
                    continue
                block_free = free[x:x + w, z:z + d]
                if not block_free.all():
                    continue
                if not (cids[x:x + w, z:z + d] == cid).all():
                    continue
                score = float(w * d)
                if seams_below:
                    aligned = sum(1 for dz in range(d)
                                  if (x + w, z + dz) in seams_below)
                    score -= SEAM_PENALTY * aligned
                if support is not None and not support[x:x + w, z:z + d].any():
                    score -= UNSUPPORTED_PENALTY
                if score > best_score:
                    best_score, best = score, (brick.part_id, rot, w, d)
        if best is None:                     # a single stud always fits
            return ("3005", 0, 1, 1)
        return best
