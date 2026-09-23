"""Settings, size presets and the branding/legal text.

Brand wording lives here rather than in the UI because the brief requires it
to be configurable: what we sell is a set of LEGO-*compatible* bricks, and
nothing in the product may imply that The LEGO Group makes it, endorses it or
has anything to do with it.  The app reads these strings from the server, so
the wording can be corrected in one place if counsel asks -- including going
the other way, should a licence ever exist.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict, field


@dataclass(frozen=True)
class SizePreset:
    """A size the user can pick, and what it means behind the scenes."""

    key: str
    label: str
    width_studs: int         # starting width; the builder adjusts to the budget
    max_pieces: int
    max_dimension_cm: float
    colors: int              # palette size; more colours means more detail
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


SIZE_PRESETS = (
    SizePreset("mini",    "Mini",    12,   180,  12.0,  6,  "simple"),
    SizePreset("small",   "Small",   16,   400,  16.0,  8,  "balanced"),
    SizePreset("medium",  "Medium",  24,   900,  22.0, 12,  "balanced"),
    SizePreset("large",   "Large",   32,  1800,  30.0, 16,  "detailed"),
    SizePreset("display", "Display", 48,  4500,  42.0, 20,  "detailed"),
)
PRESETS_BY_KEY = {p.key: p for p in SIZE_PRESETS}
DEFAULT_PRESET = "medium"

# Custom sizes are asked for as a width in centimetres.  The width is a
# target, not a promise: the builder still measures what it lays and the
# model reports the dimensions it actually has.
CUSTOM_WIDTHS_CM = (10, 20, 30, 40)
CUSTOM_MIN_CM, CUSTOM_MAX_CM = 8.0, 48.0


def custom_preset(width_cm: float) -> SizePreset:
    """A size preset for "about this wide", scaled from Medium.

    Piece count grows with roughly the 2.6th power of the width (the same
    exponent the builder uses to correct itself), so the budget follows the
    width instead of being a fixed number that a 40 cm model would blow.
    """
    from .library.bricks import STUD_MM
    cm = min(CUSTOM_MAX_CM, max(CUSTOM_MIN_CM, float(width_cm)))
    studs = max(8, int(round(cm * 10.0 / STUD_MM)))
    base = PRESETS_BY_KEY["medium"]
    budget = int(base.max_pieces * (studs / float(base.width_studs)) ** 2.6)
    colors = 8 if cm <= 12 else 12 if cm <= 24 else 16
    return SizePreset("custom", "Custom (%g cm)" % cm, studs,
                      max(150, min(budget, 7000)),
                      # Width is what was asked for; height follows the
                      # subject's proportions, so it is not what binds.
                      cm * 3.0, colors, "balanced")


# What the customer says they are photographing, and how that steers the
# reconstruction.  A vision model, when configured, judges depth itself and
# gets the category only as a hint; without one, the category is the best
# information there is about how deep the unseen side should be.
CATEGORY_STRATEGIES = {
    "pet":       {"label": "Pet", "depth_profile": "rounded", "depth_ratio": 0.45,
                  "hint": "an animal, usually a pet; keep the head, ears and tail readable"},
    "person":    {"label": "Person", "depth_profile": "rounded", "depth_ratio": 0.35,
                  "hint": "a person; favour a clear face and pose over background"},
    "vehicle":   {"label": "Vehicle", "depth_profile": "boxy", "depth_ratio": 0.45,
                  "hint": "a vehicle; keep wheels and body lines, sides are parallel"},
    "building":  {"label": "Building", "depth_profile": "boxy", "depth_ratio": 0.7,
                  "hint": "a building; walls are flat and vertical, roof lines matter"},
    "object":    {"label": "Object", "depth_profile": "rounded", "depth_ratio": 0.6,
                  "hint": "an everyday object"},
    "character": {"label": "Character", "depth_profile": "rounded", "depth_ratio": 0.4,
                  "hint": "a character or figure; exaggerated head, bold colours"},
    "other":     {"label": "Other", "depth_profile": None, "depth_ratio": None, "hint": ""},
}

# How the detail answer moves the palette and the piece budget.
DETAIL_MODIFIERS = {
    "simple":   {"colors": 0.6, "pieces": 0.7, "despeckle": 11.0},
    "balanced": {"colors": 1.0, "pieces": 1.0, "despeckle": 7.0},
    "detailed": {"colors": 1.5, "pieces": 1.35, "despeckle": 4.0},
}

# How the appearance/strength answer moves the build.
#
# The lattice spacing matters far less than it looks like it should. Hollowing
# saves cells, but every cell it removes from under the skin leaves a brick
# with nothing to rest on, and the support pass puts most of them back: on a
# test photograph a hollow volume went 666 cells -> 1197 after grounding,
# landing within 1% of the solid build's piece count. So this is a weight and
# material dial, not a cost one. A wider lattice is kept as the default
# because it is marginally lighter and marginally cheaper.
PRIORITY_MODIFIERS = {
    # shell: how thick the skin is; lattice: spacing of the internal walls
    "appearance": {"shell": 1, "lattice": 6, "solid": False, "stagger": True},
    "balanced":   {"shell": 1, "lattice": 6, "solid": False, "stagger": True},
    "strength":   {"shell": 2, "lattice": 4, "solid": False, "stagger": True},
}


@dataclass
class Branding:
    """Wording the app must show.  Configurable, per the brief's section 20."""

    product_name: str = "Kitsnap"
    brick_term: str = "LEGO-compatible bricks"
    disclaimer: str = (
        "Kitsnap is not affiliated with, authorised by or endorsed by The "
        "LEGO Group. LEGO is a trademark of The LEGO Group, which does not "
        "sponsor or endorse this app. Sets are built from LEGO-compatible "
        "elements."
    )
    short_disclaimer: str = "Built from LEGO-compatible bricks. Not a LEGO Group product."
    official_product: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Settings:
    data_dir: str = os.environ.get("BRICKSNAP_DATA", "./data")
    max_upload_mb: int = 12
    max_references: int = 4
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    vision_model: str = os.environ.get("BRICKSNAP_VISION_MODEL", "claude-sonnet-5")
    supplier: str = os.environ.get("BRICKSNAP_SUPPLIER", "compatible")
    branding: Branding = field(default_factory=Branding)

    def public(self) -> dict:
        """What the client is allowed to know.  The key never leaves here."""
        return {
            "product_name": self.branding.product_name,
            "branding": self.branding.to_dict(),
            "size_presets": [p.to_dict() for p in SIZE_PRESETS],
            "default_preset": DEFAULT_PRESET,
            "max_references": self.max_references,
            "max_upload_mb": self.max_upload_mb,
            "vision_enabled": bool(self.anthropic_api_key),
        }


SETTINGS = Settings()
