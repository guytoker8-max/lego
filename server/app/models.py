"""The structured brick model.

This is the spine of the product.  The 3D preview, the parts list, the
instructions and the physical kit are all renderings of *this* object, never
of each other and never of the photo.  If they can disagree, the promise
("a LEGO set you can actually build") is broken, so every stage reads and
writes this one structure.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Iterable

from .library import LIBRARY, BrickLibrary, STUD_MM, PLATE_MM, color_by_id


@dataclass(frozen=True)
class PlacedBrick:
    """One element, in one colour, at one place, in one orientation."""

    part_id: str
    color_id: int
    x: int              # stud column, left edge
    y: int              # plate unit, bottom face
    z: int              # stud row, near edge
    rotation: int = 0   # 0 or 90 degrees about y

    def brick(self, library: BrickLibrary = LIBRARY):
        return library.get(self.part_id)

    def cells(self, library: BrickLibrary = LIBRARY) -> Iterable[tuple]:
        return self.brick(library).cells(self.x, self.y, self.z, self.rotation)

    def footprint(self, library: BrickLibrary = LIBRARY) -> tuple:
        return self.brick(library).footprint(self.rotation)

    def top_y(self, library: BrickLibrary = LIBRARY) -> int:
        return self.y + self.brick(library).h

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlacedBrick":
        return cls(d["part_id"], d["color_id"], d["x"], d["y"], d["z"],
                   d.get("rotation", 0))


@dataclass
class BuildStep:
    """One page of the instruction booklet."""

    index: int                  # 1-based
    title: str
    brick_indices: list         # indices into BrickModel.bricks
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BrickModel:
    """A complete, buildable model."""

    name: str
    subject: str = ""
    bricks: list = field(default_factory=list)      # list[PlacedBrick]
    steps: list = field(default_factory=list)       # list[BuildStep]
    size_studs: tuple = (0, 0, 0)                   # (x, y-plates, z)
    source: dict = field(default_factory=dict)      # analysis + settings used
    validation: dict = field(default_factory=dict)  # last ValidationReport
    library: BrickLibrary = field(default=LIBRARY, repr=False, compare=False)

    # ---- geometry --------------------------------------------------------

    @property
    def piece_count(self) -> int:
        return len(self.bricks)

    @property
    def color_ids(self) -> list:
        return sorted({b.color_id for b in self.bricks})

    @property
    def dimensions_mm(self) -> tuple:
        x, y, z = self.size_studs
        return (round(x * STUD_MM, 1), round(y * PLATE_MM, 1), round(z * STUD_MM, 1))

    @property
    def dimensions_cm(self) -> tuple:
        return tuple(round(v / 10.0, 1) for v in self.dimensions_mm)

    @property
    def weight_g(self) -> float:
        lib = self.library
        return round(sum(lib.get(b.part_id).weight_g for b in self.bricks), 1)

    def occupancy(self) -> dict:
        """cell -> brick index.  The truth about what sits where."""
        cells = {}
        for i, b in enumerate(self.bricks):
            for c in b.cells(self.library):
                cells[c] = i
        return cells

    def bricks_by_layer(self) -> dict:
        layers = {}
        for i, b in enumerate(self.bricks):
            layers.setdefault(b.y, []).append(i)
        return layers

    # ---- identity --------------------------------------------------------

    def fingerprint(self) -> str:
        """Stable hash of the built structure.

        The parts list, the instructions and the physical kit all carry this.
        If two of them disagree, the fingerprints differ and we can tell.
        """
        payload = sorted(
            (b.part_id, b.color_id, b.x, b.y, b.z, b.rotation) for b in self.bricks
        )
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    # ---- serialisation ---------------------------------------------------

    def to_dict(self, *, include_steps: bool = True) -> dict:
        out = {
            "name": self.name,
            "subject": self.subject,
            "fingerprint": self.fingerprint(),
            "size_studs": list(self.size_studs),
            "dimensions_cm": list(self.dimensions_cm),
            "piece_count": self.piece_count,
            "color_count": len(self.color_ids),
            "weight_g": self.weight_g,
            "bricks": [b.to_dict() for b in self.bricks],
            "source": self.source,
            "validation": self.validation,
        }
        if include_steps:
            out["steps"] = [s.to_dict() for s in self.steps]
        return out

    @classmethod
    def from_dict(cls, d: dict, library: BrickLibrary = LIBRARY) -> "BrickModel":
        m = cls(
            name=d["name"],
            subject=d.get("subject", ""),
            bricks=[PlacedBrick.from_dict(b) for b in d.get("bricks", [])],
            steps=[BuildStep(**s) for s in d.get("steps", [])],
            size_studs=tuple(d.get("size_studs", (0, 0, 0))),
            source=d.get("source", {}),
            validation=d.get("validation", {}),
            library=library,
        )
        return m


@dataclass
class BomLine:
    """One line of the bill of materials: a part, a colour, a count."""

    part_id: str
    part_name: str
    color_id: int
    color_name: str
    color_hex: str
    quantity: int
    unit_weight_g: float
    unit_cost: float

    @property
    def line_weight_g(self) -> float:
        return round(self.unit_weight_g * self.quantity, 1)

    @property
    def line_cost(self) -> float:
        return round(self.unit_cost * self.quantity, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["line_weight_g"] = self.line_weight_g
        d["line_cost"] = self.line_cost
        return d


@dataclass
class Analysis:
    """What the reference images told us about the subject."""

    subject: str = "model"
    display_name: str = "Model"
    description: str = ""
    symmetry: str = "none"           # "none" | "left-right" | "radial"
    depth_profile: str = "rounded"   # "flat" | "rounded" | "boxy" | "deep"
    depth_ratio: float = 0.6         # depth as a fraction of width
    components: list = field(default_factory=list)
    dominant_colors: list = field(default_factory=list)
    confidence: float = 0.5
    questions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    source: str = "heuristic"        # "vision" | "heuristic"

    def to_dict(self) -> dict:
        return asdict(self)
