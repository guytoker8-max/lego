"""Cover the stud grid with real LEGO plates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from .parts import BY_KEY, Part


@dataclass(frozen=True)
class Placement:
    col: int            # 0-indexed column of the left edge, in the full grid
    row: int            # 0-indexed row of the top edge, in the full grid
    w: int              # studs wide
    h: int              # studs tall
    part: Part
    color_index: int
    panel: int = 0

    @property
    def size_name(self) -> str:
        """Canonical plate name, e.g. a 4-wide 2-tall plate is a "2x4"."""
        return "%dx%d" % (min(self.w, self.h), max(self.w, self.h))

    @property
    def orientation(self) -> str:
        if self.w == self.h:
            return ""
        return "across" if self.w > self.h else "down"

    def coords(self) -> str:
        """Human readable footprint, 1-indexed, as the instructions print it."""
        c0, r0 = self.col + 1, self.row + 1
        c1, r1 = self.col + self.w, self.row + self.h
        if self.w == 1 and self.h == 1:
            return "(%d,%d)" % (c0, r0)
        return "(%d,%d)-(%d,%d)" % (c0, r0, c1, r1)


@dataclass(frozen=True)
class Panel:
    index: int
    col: int            # left edge in the full grid
    row: int            # top edge in the full grid
    w: int
    h: int

    @property
    def label(self) -> str:
        return "Panel %d" % (self.index + 1)


def split_panels(width: int, height: int, panel_size: int = 0) -> list:
    """Chop the mosaic into baseplate-sized panels (0 = a single panel)."""
    if not panel_size or panel_size <= 0:
        return [Panel(0, 0, 0, width, height)]
    panels, i = [], 0
    for row in range(0, height, panel_size):
        for col in range(0, width, panel_size):
            panels.append(Panel(i, col, row,
                                min(panel_size, width - col),
                                min(panel_size, height - row)))
            i += 1
    return panels


def tile(indices: np.ndarray, catalog: tuple, panels=None) -> list:
    """Greedy maximal-plate tiling.

    Raster-scans the grid and drops the largest plate from ``catalog`` that
    fits entirely inside one uncovered, single-colour rectangle.  Plates never
    cross a panel boundary, so each panel is independently buildable.
    """
    h, w = indices.shape
    if panels is None:
        panels = [Panel(0, 0, 0, w, h)]

    # candidate footprints, largest first; squarer plates win ties
    cands = []
    for p in catalog:
        for (cw, ch) in {(p.w, p.h), (p.h, p.w)}:
            cands.append((cw, ch, p))
    cands.sort(key=lambda t: (-(t[0] * t[1]), abs(t[0] - t[1]), -t[0]))

    covered = np.zeros((h, w), dtype=bool)
    out = []
    for panel in panels:
        for r in range(panel.row, panel.row + panel.h):
            for c in range(panel.col, panel.col + panel.w):
                if covered[r, c]:
                    continue
                color = indices[r, c]
                max_w = panel.col + panel.w - c
                max_h = panel.row + panel.h - r
                for cw, ch, part in cands:
                    if cw > max_w or ch > max_h:
                        continue
                    block = indices[r:r + ch, c:c + cw]
                    if not np.all(block == color):
                        continue
                    if covered[r:r + ch, c:c + cw].any():
                        continue
                    covered[r:r + ch, c:c + cw] = True
                    out.append(Placement(col=c, row=r, w=cw, h=ch, part=part,
                                         color_index=int(color),
                                         panel=panel.index))
                    break
    assert covered.all(), "tiler left holes -- catalog must contain a 1x1 plate"
    return out


def bill_of_materials(placements, palette) -> list:
    """Parts list: one row per (plate size, colour), most used first."""
    counts = Counter((p.part.key, p.color_index) for p in placements)
    rows = []
    for (key, cidx), n in counts.items():
        colour = palette[cidx]
        rows.append({
            "part": "Plate %dx%d" % key,
            "design_id": BY_KEY[key].design_id,
            "color_name": colour.name,
            "color_id": colour.id,
            "color_hex": colour.hex,
            "quantity": n,
            "studs": key[0] * key[1] * n,
        })
    rows.sort(key=lambda r: (-r["studs"], r["color_name"], r["part"]))
    return rows


def color_usage(indices: np.ndarray, palette) -> list:
    """Stud count per colour, most used first."""
    vals, counts = np.unique(indices, return_counts=True)
    total = int(indices.size)
    rows = [{"color_name": palette[int(v)].name, "color_id": palette[int(v)].id,
             "color_hex": palette[int(v)].hex, "studs": int(n),
             "share": float(n) / total} for v, n in zip(vals, counts)]
    rows.sort(key=lambda r: -r["studs"])
    return rows


def make_steps(placements, panels, band_rows: int = 2, max_parts: int = 14) -> list:
    """Group plates into buildable steps: panel by panel, band by band."""
    steps = []
    for panel in panels:
        mine = [p for p in placements if p.panel == panel.index]
        mine.sort(key=lambda p: (p.row, p.col))
        bands = {}
        for p in mine:
            band = (p.row - panel.row) // band_rows
            bands.setdefault(band, []).append(p)
        for band in sorted(bands):
            group = bands[band]
            for i in range(0, len(group), max_parts):
                steps.append({"panel": panel, "placements": group[i:i + max_parts]})
    for n, s in enumerate(steps, 1):
        s["number"] = n
    return steps
