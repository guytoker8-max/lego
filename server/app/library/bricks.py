"""The brick library: every element the generator is allowed to use.

Nothing downstream may invent a part.  A brick exists here, with real
dimensions, real connection points, a weight and a cost, or it cannot appear
in a model.  ``BrickLibrary`` is the single gate.

Geometry convention used across the whole app
---------------------------------------------
The model lives on an integer grid.

* x, z  are stud columns.  1 stud = 8.0 mm.
* y     is *plate* units, counted upward from the baseplate.  1 plate = 3.2 mm.
  A standard brick is 3 plate units tall (9.6 mm), a plate is 1, a tile is 1.

Keeping y in plate units means plates and bricks share one coordinate system,
so a later phase can mix them without regrinding the model.

A part's footprint is ``w x d`` studs at rotation 0.  Rotation is 0 or 90
degrees about y; 90 swaps w and d.  LEGO bricks are symmetric under 180, so
those are the only two distinct orientations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

STUD_MM = 8.0            # stud pitch
PLATE_MM = 3.2           # one plate unit of height
BRICK_PLATES = 3         # a standard brick is three plates tall


@dataclass(frozen=True)
class Brick:
    """One element type, independent of colour."""

    part_id: str             # LEGO / BrickLink design number
    name: str                # human name, e.g. "Brick 2x4"
    w: int                   # studs along x at rotation 0
    d: int                   # studs along z at rotation 0
    h: int                   # height in plate units
    kind: str                # "brick" | "plate" | "tile" | "baseplate"
    weight_g: float          # grams, one element
    base_cost: float         # supplier cost per element, ILS, before colour
    has_studs: bool = True   # tiles are flat on top: nothing stacks on them
    tier: str = "core"       # "core" parts are stocked everywhere

    # ---- derived geometry ------------------------------------------------

    @property
    def studs(self) -> int:
        return self.w * self.d

    @property
    def volume(self) -> int:
        """Grid cells occupied: footprint x height in plate units."""
        return self.w * self.d * self.h

    @property
    def key(self) -> tuple:
        return (self.kind, min(self.w, self.d), max(self.w, self.d), self.h)

    def size_mm(self, rotation: int = 0) -> tuple:
        w, d = self.footprint(rotation)
        return (w * STUD_MM, self.h * PLATE_MM, d * STUD_MM)

    def footprint(self, rotation: int = 0) -> tuple:
        """(w, d) in studs for a rotation of 0 or 90 degrees."""
        return (self.d, self.w) if rotation % 180 == 90 else (self.w, self.d)

    def cells(self, x: int, y: int, z: int, rotation: int = 0) -> Iterable[tuple]:
        """Every grid cell this element fills when placed at (x, y, z)."""
        w, d = self.footprint(rotation)
        for dy in range(self.h):
            for dz in range(d):
                for dx in range(w):
                    yield (x + dx, y + dy, z + dz)

    def top_studs(self, x: int, z: int, rotation: int = 0) -> Iterable[tuple]:
        """Stud positions on the element's top face, as (x, z) with y above."""
        if not self.has_studs:
            return ()
        w, d = self.footprint(rotation)
        return (
            (x + dx, z + dz)
            for dz in range(d)
            for dx in range(w)
        )

    def rotations(self) -> tuple:
        """Distinct orientations.  A square part has only one."""
        return (0,) if self.w == self.d else (0, 90)


# ---------------------------------------------------------------------------
# The catalog
# ---------------------------------------------------------------------------
# Costs are supplier-side per-element estimates in ILS for LEGO-compatible
# elements bought in bulk; they are overridden per supplier at pricing time
# (see library/suppliers.py).  Weights are the published element weights.

def _b(part_id, w, d, h, kind, weight, cost, tier="core", has_studs=True):
    label = {"brick": "Brick", "plate": "Plate", "tile": "Tile",
             "baseplate": "Baseplate"}[kind]
    name = "%s %dx%d" % (label, min(w, d), max(w, d))
    return Brick(part_id, name, w, d, h, kind, weight, cost, has_studs, tier)


CATALOG: tuple = (
    # --- bricks, 3 plates tall ------------------------------------------
    _b("3005", 1, 1, 3, "brick", 0.45, 0.30),
    _b("3004", 2, 1, 3, "brick", 0.80, 0.32),
    _b("3622", 3, 1, 3, "brick", 1.15, 0.38),
    _b("3010", 4, 1, 3, "brick", 1.50, 0.42),
    _b("3009", 6, 1, 3, "brick", 2.20, 0.55),
    _b("3008", 8, 1, 3, "brick", 2.90, 0.70),
    _b("3003", 2, 2, 3, "brick", 1.30, 0.38),
    _b("3002", 3, 2, 3, "brick", 1.90, 0.46),
    _b("3001", 4, 2, 3, "brick", 2.50, 0.52),
    _b("2456", 6, 2, 3, "brick", 3.70, 0.72),
    _b("3007", 8, 2, 3, "brick", 4.90, 0.95),

    # --- plates, 1 plate tall -------------------------------------------
    _b("3024", 1, 1, 1, "plate", 0.16, 0.22),
    _b("3023", 2, 1, 1, "plate", 0.28, 0.24),
    _b("3623", 3, 1, 1, "plate", 0.40, 0.28),
    _b("3710", 4, 1, 1, "plate", 0.52, 0.30),
    _b("3666", 6, 1, 1, "plate", 0.76, 0.40),
    _b("3460", 8, 1, 1, "plate", 1.00, 0.50),
    _b("3022", 2, 2, 1, "plate", 0.50, 0.28),
    _b("3021", 3, 2, 1, "plate", 0.72, 0.34),
    _b("3020", 4, 2, 1, "plate", 0.95, 0.38),
    _b("3795", 6, 2, 1, "plate", 1.40, 0.52),
    _b("3034", 8, 2, 1, "plate", 1.85, 0.68),
    _b("3031", 4, 4, 1, "plate", 1.85, 0.62),
    _b("3032", 6, 4, 1, "plate", 2.75, 0.85),
    _b("3035", 8, 4, 1, "plate", 3.60, 1.10),
    _b("3958", 6, 6, 1, "plate", 4.10, 1.25),
    _b("3036", 8, 6, 1, "plate", 5.40, 1.60),
    _b("41539", 8, 8, 1, "plate", 7.20, 2.10),

    # --- tiles: smooth finish, nothing stacks on them --------------------
    _b("3070", 1, 1, 1, "tile", 0.14, 0.26, "detail", has_studs=False),
    _b("3069", 2, 1, 1, "tile", 0.25, 0.28, "detail", has_studs=False),
    _b("3068", 2, 2, 1, "tile", 0.45, 0.34, "detail", has_studs=False),

    # --- baseplates: the board a model stands on -------------------------
    _b("3857", 16, 16, 1, "baseplate", 12.0, 9.0, "base"),
    _b("4186", 48, 48, 1, "baseplate", 96.0, 42.0, "base"),
)

BY_PART_ID = {b.part_id: b for b in CATALOG}


class BrickLibrary:
    """The only source of parts.  Ask it; never hard-code an element."""

    def __init__(self, catalog: tuple = CATALOG, availability: dict | None = None):
        self._catalog = tuple(catalog)
        self._by_id = {b.part_id: b for b in self._catalog}
        # availability: part_id -> stocked units, or None for "assume stocked"
        self._availability = availability or {}

    # ---- lookup ---------------------------------------------------------

    def get(self, part_id: str) -> Brick:
        try:
            return self._by_id[part_id]
        except KeyError:
            raise UnknownPartError(part_id) from None

    def exists(self, part_id: str) -> bool:
        return part_id in self._by_id

    def all(self) -> tuple:
        return self._catalog

    def available(self, part_id: str, quantity: int = 1) -> bool:
        stock = self._availability.get(part_id)
        return True if stock is None else stock >= quantity

    # ---- selection ------------------------------------------------------

    def building_set(self, *, max_length: int = 8, max_width: int = 2,
                     kinds: tuple = ("brick",)) -> tuple:
        """The elements a generator may place, largest first.

        Largest-first is what the tiler wants: covering a run of eight studs
        with one 2x8 beats eight 1x1s on cost, part count and build time.
        """
        out = [
            b for b in self._catalog
            if b.kind in kinds
            and max(b.w, b.d) <= max_length
            and min(b.w, b.d) <= max_width
            and self.available(b.part_id)
        ]
        if not out:
            out = [self.get("3005")]
        return tuple(sorted(out, key=lambda b: (-b.studs, abs(b.w - b.d))))

    def baseplate_for(self, w: int, d: int) -> Brick:
        for b in sorted((x for x in self._catalog if x.kind == "baseplate"),
                        key=lambda x: x.studs):
            if b.w >= w and b.d >= d:
                return b
        return self.get("4186")


class UnknownPartError(KeyError):
    """Raised when anything asks for a part the library does not stock.

    This is the guard that stops a model containing an element nobody can
    actually ship.
    """

    def __init__(self, part_id: str):
        super().__init__(part_id)
        self.part_id = part_id

    def __str__(self) -> str:
        return "no such part in the brick library: %r" % self.part_id


LIBRARY = BrickLibrary()
