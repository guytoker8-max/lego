"""Stage 5 - BrickOptimizer.

Makes the model cheaper to buy and quicker to build without changing what it
looks like.  Three things do nearly all the work:

*Hollowing.*  A solid model is mostly bricks nobody will ever see, and they
are most of the cost and most of the build time.  Real sets are shells.  We
keep the visible skin, run an internal lattice so the shell has something to
hold on to, and throw the rest away.

*Colour despeckling.*  Shrinking a photo leaves single odd cells along every
edge -- one stray green stud between blue and white.  Each becomes a 1x1, the
priciest way to buy a stud.  A lone cell is swapped to its neighbours' colour
when the swap is nearly free perceptually, which the CIEDE2000 distance tells
us, so real single-stud detail survives.

Nothing here is allowed to make the model unbuildable; the validator runs
after it and has the last word.
"""

from __future__ import annotations

import numpy as np

from ..library import DEFAULT_COLORS, ColorLibrary
from ..vendor.legoize import palette as _lego
from .geometry import Volume

class BrickOptimizer:
    def __init__(self, colors: ColorLibrary = DEFAULT_COLORS):
        self.colors = colors

    # ---- volume level ----------------------------------------------------

    def hollow(self, volume: Volume, *, shell: int = 1,
               lattice: int = 4, keep_solid: bool = False) -> Volume:
        """Empty the inside, keeping a skin and an internal lattice.

        ``shell`` is the skin thickness in cells; ``lattice`` is the spacing
        of the internal walls that stop the skin from being a bag.  A model
        thinner than 2*shell+1 anywhere is left solid there, because there is
        no inside to remove.
        """
        if keep_solid:
            return volume

        solid = volume.solid
        keep = volume.visible()
        for _ in range(shell - 1):
            keep = _dilate(keep) & solid

        X, Y, Z = solid.shape
        walls = np.zeros_like(solid)
        # Walls in one direction only. A cross-hatch of one-cell walls looks
        # stronger and builds far worse: every intersection and every spur is
        # a cell with no neighbour along either axis, which is a 1x1 brick.
        # Full planes in a single direction tie the front skin to the back
        # one just as well, and each plane tiles into long bricks.
        walls[:, :, ::lattice] = True
        walls[:, 0, :] = True                # the model sits on its footprint
        keep |= solid & walls

        keep = self._prop_supports(solid, keep)

        out = Volume(solid=solid & keep, rgb=volume.rgb.copy(),
                     layer_plates=volume.layer_plates)
        out.rgb[~out.solid] = 0
        return out

    def _prop_supports(self, solid: np.ndarray, keep: np.ndarray) -> np.ndarray:
        """Put something under every cell hollowing left hanging.

        Emptying the inside of a shell leaves the skin of an overhang with
        nothing beneath it. The validator would notice and prop each one with
        a 1x1 column, which works but buys the most expensive element in the
        catalogue by the hundred. Restoring the solid cell directly beneath
        instead costs nothing -- it was going to be thrown away -- and it
        tiles into ordinary long bricks with everything around it.

        Top down in one pass: a cell restored at layer y is itself checked
        against layer y-1 on the next iteration.
        """
        out = keep.copy()
        X, Y, Z = solid.shape
        for y in range(Y - 1, 0, -1):
            hanging = out[:, y, :] & ~out[:, y - 1, :]
            out[:, y - 1, :] |= hanging & solid[:, y - 1, :]
        return out

    def ground_overhangs(self, volume: Volume) -> Volume:
        """Put something under the parts that would otherwise hang in the air.

        Carefully, though. Support is needed by *bricks*, not by cells: a
        layer of a hollow shell is a closed ring sitting on the slightly
        wider ring below it, and although each ring's inner edge overhangs,
        every brick in it also covers outer cells that are supported. Filling
        under each overhanging cell would refill the whole inside and undo
        the hollowing completely.

        So a region is only propped when *nothing* in it reaches the layer
        below -- a floating cap, a raised limb. Whatever slips through is
        caught by the validator afterwards, which is the authority; this pass
        exists to make its job small, and to keep support inside the piece
        budget rather than arriving after it was measured.
        """
        solid = volume.solid.copy()
        rgb = volume.rgb.copy()
        X, Y, Z = solid.shape
        for y in range(Y - 1, 0, -1):
            layer = solid[:, y, :]
            below = solid[:, y - 1, :]
            if not layer.any():
                continue
            floating = layer & ~below
            if not floating.any():
                continue
            need = np.zeros_like(layer)
            for comp in _components_2d(layer):
                if not (comp & below).any():     # nothing in it touches down
                    need |= comp & floating
            if not need.any():
                continue
            solid[:, y - 1, :] |= need
            patch = rgb[:, y - 1, :, :]
            patch[need] = rgb[:, y, :, :][need]
        out = Volume(solid=solid, rgb=rgb, layer_plates=volume.layer_plates)
        out.rgb[~solid] = 0
        return out

    def ground_bricks(self, volume: Volume, bricks: list, library) -> tuple:
        """Fill in under bricks that have nothing to rest on.

        Cell-level grounding cannot decide this, because support is a
        property of a brick: a 1x8 spanning a ring needs only one of its
        eight studs to land on something. So the question is only answerable
        once the bricks exist -- which is why this runs after a trial tiling
        and the volume is then tiled again.

        A whole footprint is filled, not a single column, because a footprint
        is contiguous: the cells added sit next to each other and next to the
        shell, so they tile into ordinary long bricks. The validator's own
        repair does the same job with a 1x1 column per brick, which works but
        buys the most expensive element in the catalogue; leaving it with
        nothing to do is the point.

        Returns (volume, number of footprints filled).
        """
        solid = volume.solid.copy()
        rgb = volume.rgb.copy()
        filled = 0
        for b in sorted(bricks, key=lambda x: x.y):
            if b.y == 0:
                continue
            y = b.y // 3
            if y <= 0:
                continue
            brick = library.get(b.part_id)
            w, d = brick.footprint(b.rotation)
            foot = np.zeros(solid.shape[0::2], dtype=bool)
            foot[b.x:b.x + w, b.z:b.z + d] = True
            if (solid[:, y - 1, :] & foot).any():
                continue                     # it already rests on something
            solid[:, y - 1, :] |= foot
            patch = rgb[:, y - 1, :, :]
            patch[foot] = rgb[:, y, :, :][foot]
            filled += 1
        out = Volume(solid=solid, rgb=rgb, layer_plates=volume.layer_plates)
        out.rgb[~solid] = 0
        return out, filled

    def merge_short_runs(self, cids: np.ndarray, solid: np.ndarray,
                         threshold: float = 8.0) -> np.ndarray:
        """Absorb one- and two-cell colour runs into the run beside them.

        A photo reduced to a stud grid leaves short runs along every colour
        boundary, and a short run is bought as 1x1 and 1x2 bricks -- the most
        expensive studs in the set, and the slowest to place. Where the two
        sides of a short run are the same colour and the swap is perceptually
        near-free, the run is absorbed and the two neighbours become one long
        brick.

        Both directions are swept, because a run that is short across is
        often long along, and only the short way should be merged.
        """
        out = cids.copy()
        X, Y, Z = out.shape
        lab = {c.id: _lego.srgb_to_lab(np.array(c.rgb, dtype=np.uint8))
               for c in self.colors.colors}

        for y in range(Y):
            layer = solid[:, y, :]
            if not layer.any():
                continue
            plane = out[:, y, :]
            self._merge_lines(plane, layer, lab, threshold, axis=0)
            self._merge_lines(plane, layer, lab, threshold, axis=1)
            out[:, y, :] = plane
        return out

    def _merge_lines(self, plane: np.ndarray, layer: np.ndarray, lab: dict,
                     threshold: float, axis: int) -> None:
        n = plane.shape[axis]
        other = plane.shape[1 - axis]
        for i in range(other):
            line = plane[:, i] if axis == 0 else plane[i, :]
            mask = layer[:, i] if axis == 0 else layer[i, :]
            for start, length, value in _runs(line, mask):
                if length > 2:
                    continue
                before = int(line[start - 1]) if start > 0 and mask[start - 1] else None
                after_i = start + length
                after = (int(line[after_i])
                         if after_i < n and mask[after_i] else None)
                if before is None or before != after:
                    continue
                if value not in lab or before not in lab:
                    continue
                d = float(_lego.delta_e_2000(lab[value][None, :],
                                             lab[before][None, :])[0])
                if d <= threshold:
                    line[start:after_i] = before

    # ---- colour level ----------------------------------------------------

    def despeckle(self, cids: np.ndarray, solid: np.ndarray,
                  threshold: float = 7.0, passes: int = 2) -> np.ndarray:
        """Swap isolated colour cells into their neighbours, when it is cheap.

        ``threshold`` is a CIEDE2000 distance: below about 7 the swap is
        invisible at arm's length, which is how a mosaic is read.
        """
        out = cids.copy()
        lab = {c.id: _lego.srgb_to_lab(np.array(c.rgb, dtype=np.uint8))
               for c in self.colors.colors}
        X, Y, Z = out.shape

        for _ in range(passes):
            changed = 0
            neigh = _neighbour_ids(out, solid)
            for (x, y, z), (best_id, count) in neigh.items():
                mine = int(out[x, y, z])
                # Three of six neighbours is already a clear majority in a
                # shell, where two of the six are usually air. Requiring four
                # meant this pass almost never fired.
                if best_id == mine or count < 3:
                    continue
                if mine not in lab or best_id not in lab:
                    continue
                d = float(_lego.delta_e_2000(lab[mine][None, :],
                                             lab[best_id][None, :])[0])
                if d <= threshold:
                    out[x, y, z] = best_id
                    changed += 1
            if not changed:
                break
        return out

    # ---- brick level -----------------------------------------------------

    def summarise(self, before: int, after: int) -> dict:
        saved = before - after
        return {"cells_before": before, "pieces_after": after,
                "pieces_saved": saved,
                "reduction": round(saved / before, 3) if before else 0.0}


def _dilate(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :, :] |= mask[:-1, :, :]
    out[:-1, :, :] |= mask[1:, :, :]
    out[:, 1:, :] |= mask[:, :-1, :]
    out[:, :-1, :] |= mask[:, 1:, :]
    out[:, :, 1:] |= mask[:, :, :-1]
    out[:, :, :-1] |= mask[:, :, 1:]
    return out


def _neighbour_ids(cids: np.ndarray, solid: np.ndarray) -> dict:
    """For each solid cell, the most common colour among its 6 neighbours.

    Only cells whose own colour is in a minority are reported, since those
    are the ones a swap would help.
    """
    X, Y, Z = cids.shape
    result = {}
    shifts = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    xs, ys, zs = np.nonzero(solid)
    for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
        counts = {}
        for dx, dy, dz in shifts:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < X and 0 <= ny < Y and 0 <= nz < Z and solid[nx, ny, nz]:
                cid = int(cids[nx, ny, nz])
                counts[cid] = counts.get(cid, 0) + 1
        if not counts:
            continue
        best_id = max(counts, key=counts.get)
        mine = int(cids[x, y, z])
        if counts.get(mine, 0) < counts[best_id]:
            result[(x, y, z)] = (best_id, counts[best_id])
    return result


def _runs(line: np.ndarray, mask: np.ndarray):
    """Maximal same-value runs of solid cells: (start, length, value)."""
    start = None
    value = None
    for i in range(len(line)):
        v = int(line[i]) if mask[i] else None
        if v != value:
            if value is not None and start is not None:
                yield (start, i - start, value)
            start, value = (i, v) if v is not None else (None, None)
    if value is not None and start is not None:
        yield (start, len(line) - start, value)


def _components_2d(mask: np.ndarray):
    """4-connected regions of a layer, as boolean masks."""
    remaining = mask.copy()
    guard = 0
    while remaining.any() and guard < 2000:
        guard += 1
        xs, zs = np.nonzero(remaining)
        seed = np.zeros_like(remaining)
        seed[xs[0], zs[0]] = True
        while True:
            grown = seed.copy()
            grown[1:, :] |= seed[:-1, :]
            grown[:-1, :] |= seed[1:, :]
            grown[:, 1:] |= seed[:, :-1]
            grown[:, :-1] |= seed[:, 1:]
            grown &= remaining
            if grown.sum() == seed.sum():
                break
            seed = grown
        yield seed
        remaining &= ~seed
