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

# How the detail answer moves the palette and the piece budget.
DETAIL_MODIFIERS = {
    "simple":   {"colors": 0.6, "pieces": 0.7, "despeckle": 11.0},
    "balanced": {"colors": 1.0, "pieces": 1.0, "despeckle": 7.0},
    "detailed": {"colors": 1.5, "pieces": 1.35, "despeckle": 4.0},
}

# How the appearance/strength answer moves the build.
PRIORITY_MODIFIERS = {
    # shell: how thick the skin is; lattice: spacing of internal walls
    "appearance": {"shell": 1, "lattice": 6, "solid": False, "stagger": True},
    "balanced":   {"shell": 1, "lattice": 4, "solid": False, "stagger": True},
    "strength":   {"shell": 2, "lattice": 3, "solid": False, "stagger": True},
}


@dataclass
class Branding:
    """Wording the app must show.  Configurable, per the brief's section 20."""

    product_name: str = "BrickSnap"
    brick_term: str = "LEGO-compatible bricks"
    disclaimer: str = (
        "BrickSnap is not affiliated with, authorised by or endorsed by The "
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
