"""The real LEGO plates the mosaic is built from."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Part:
    design_id: str   # LEGO / BrickLink design number
    w: int           # studs
    h: int           # studs

    @property
    def name(self) -> str:
        return "Plate %dx%d" % (min(self.w, self.h), max(self.w, self.h))

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def key(self) -> tuple:
        return (min(self.w, self.h), max(self.w, self.h))


# Plates (1/3 brick high) that LEGO makes in a wide range of colours.
CATALOG: tuple = tuple(
    Part(design_id, a, b) for (a, b, design_id) in (
        (1, 1, "3024"), (1, 2, "3023"), (1, 3, "3623"), (1, 4, "3710"),
        (1, 6, "3666"), (1, 8, "3460"), (1, 10, "4477"), (1, 12, "60479"),
        (2, 2, "3022"), (2, 3, "3021"), (2, 4, "3020"), (2, 6, "3795"),
        (2, 8, "3034"), (2, 10, "3832"), (2, 12, "2445"), (2, 14, "91988"),
        (2, 16, "4282"),
        (4, 4, "3031"), (4, 6, "3032"), (4, 8, "3035"), (4, 10, "3030"),
        (4, 12, "3029"),
        (6, 6, "3958"), (6, 8, "3036"), (6, 10, "3033"), (6, 12, "3028"),
        (6, 14, "3456"), (6, 16, "3027"),
        (8, 8, "41539"), (8, 16, "92438"),
        (16, 16, "91405"),
    )
)

BY_KEY = {p.key: p for p in CATALOG}

BASEPLATE_IDS = {16: "91405", 32: "3857", 48: "4186"}


def build_catalog(max_studs: int = 8, only_1x1: bool = False,
                  max_width: int = 2) -> tuple:
    """Pick the plate sizes the tiler may use.

    max_studs  longest edge allowed (bigger plates = fewer parts, cheaper).
    max_width  shortest edge allowed; 2 keeps the part list to the cheap,
               ubiquitous 1xN and 2xN plates.
    """
    if only_1x1:
        return (BY_KEY[(1, 1)],)
    out = [p for p in CATALOG
           if p.key[1] <= max_studs and p.key[0] <= max_width]
    if not out:
        out = [BY_KEY[(1, 1)]]
    return tuple(sorted(out, key=lambda p: (-p.area, abs(p.w - p.h))))
