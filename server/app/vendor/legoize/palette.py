"""LEGO colour palette and perceptual colour matching.

Colour names and ids follow the LDraw / Rebrickable numbering that BrickLink,
Rebrickable and most parts shops use.  The RGB values are the widely used
community approximations of the real moulded colours -- they are good enough
to pick the right brick, but they are not spectrophotometer measurements.

Every colour listed here exists as a plate you can actually buy.  Colours are
split into two tiers:

``common``    plentiful and cheap in 1x1 .. 2x4 plates; the default palette.
``extended``  real, but rarer / pricier in small plates.  Opt in with
              ``--palette extended`` when you want maximum fidelity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np


@dataclass(frozen=True)
class LegoColor:
    id: int          # LDraw / Rebrickable colour id
    name: str        # BrickLink-style colour name
    rgb: tuple       # (r, g, b) 0-255
    tier: str        # "common" or "extended"

    @property
    def hex(self) -> str:
        return "#%02X%02X%02X" % self.rgb


# --------------------------------------------------------------------------
# The palette
# --------------------------------------------------------------------------

COLORS: tuple = (
    # --- neutrals -------------------------------------------------------
    LegoColor(15,  "White",                  (0xFF, 0xFF, 0xFF), "common"),
    LegoColor(151, "Very Light Bluish Gray", (0xE6, 0xE3, 0xE0), "common"),
    LegoColor(71,  "Light Bluish Gray",      (0xA0, 0xA5, 0xA9), "common"),
    LegoColor(72,  "Dark Bluish Gray",       (0x6C, 0x6E, 0x68), "common"),
    LegoColor(0,   "Black",                  (0x05, 0x13, 0x1D), "common"),
    LegoColor(7,   "Light Gray",             (0x9B, 0xA1, 0x9D), "extended"),
    LegoColor(8,   "Dark Gray",              (0x6D, 0x6E, 0x5C), "extended"),

    # --- reds / pinks ---------------------------------------------------
    LegoColor(4,   "Red",                    (0xC9, 0x1A, 0x09), "common"),
    LegoColor(320, "Dark Red",               (0x72, 0x0E, 0x0F), "common"),
    LegoColor(216, "Rust",                   (0xB3, 0x10, 0x04), "extended"),
    LegoColor(12,  "Salmon",                 (0xF2, 0x70, 0x5E), "extended"),
    LegoColor(100, "Light Salmon",           (0xFE, 0xBA, 0xBD), "extended"),
    LegoColor(29,  "Bright Pink",            (0xE4, 0xAD, 0xC8), "common"),
    LegoColor(13,  "Pink",                   (0xFC, 0x97, 0xAC), "extended"),
    LegoColor(351, "Medium Dark Pink",       (0xF7, 0x85, 0xB1), "extended"),
    LegoColor(5,   "Dark Pink",              (0xC8, 0x70, 0xA0), "extended"),
    LegoColor(26,  "Magenta",                (0x92, 0x39, 0x78), "common"),

    # --- purples --------------------------------------------------------
    LegoColor(30,  "Medium Lavender",        (0xAC, 0x78, 0xBA), "common"),
    LegoColor(31,  "Lavender",               (0xE1, 0xD5, 0xED), "common"),
    LegoColor(85,  "Dark Purple",            (0x3F, 0x36, 0x91), "common"),
    LegoColor(22,  "Purple",                 (0x81, 0x00, 0x7B), "extended"),
    LegoColor(373, "Sand Purple",            (0x84, 0x5E, 0x84), "extended"),

    # --- blues ----------------------------------------------------------
    LegoColor(1,   "Blue",                   (0x00, 0x55, 0xBF), "common"),
    LegoColor(272, "Dark Blue",              (0x0A, 0x34, 0x63), "common"),
    LegoColor(73,  "Medium Blue",            (0x5A, 0x93, 0xDB), "common"),
    LegoColor(212, "Bright Light Blue",      (0x9F, 0xC3, 0xE9), "common"),
    LegoColor(321, "Dark Azure",             (0x07, 0x8B, 0xC9), "common"),
    LegoColor(322, "Medium Azure",           (0x36, 0xAE, 0xBF), "common"),
    LegoColor(9,   "Light Blue",             (0xB4, 0xD2, 0xE3), "extended"),
    LegoColor(232, "Sky Blue",               (0x7D, 0xBF, 0xDD), "extended"),
    LegoColor(313, "Maersk Blue",            (0x35, 0x92, 0xC3), "extended"),
    LegoColor(379, "Sand Blue",              (0x60, 0x74, 0xA1), "common"),
    LegoColor(110, "Violet",                 (0x43, 0x54, 0xA3), "extended"),
    LegoColor(3,   "Dark Turquoise",         (0x00, 0x8F, 0x9B), "common"),
    LegoColor(323, "Light Aqua",             (0xAD, 0xC3, 0xC0), "common"),
    LegoColor(118, "Aqua",                   (0xB3, 0xD7, 0xD1), "extended"),

    # --- greens ---------------------------------------------------------
    LegoColor(2,   "Green",                  (0x23, 0x78, 0x41), "common"),
    LegoColor(288, "Dark Green",             (0x18, 0x46, 0x32), "common"),
    LegoColor(10,  "Bright Green",           (0x4B, 0x9F, 0x4A), "common"),
    LegoColor(27,  "Lime",                   (0xBB, 0xE9, 0x0B), "common"),
    LegoColor(115, "Medium Lime",            (0xC7, 0xD2, 0x3C), "extended"),
    LegoColor(326, "Yellowish Green",        (0xDF, 0xEE, 0xA5), "extended"),
    LegoColor(330, "Olive Green",            (0x77, 0x77, 0x4E), "common"),
    LegoColor(378, "Sand Green",             (0xA0, 0xBC, 0xAC), "common"),
    LegoColor(74,  "Medium Green",           (0x73, 0xDC, 0xA1), "extended"),

    # --- yellows / oranges ----------------------------------------------
    LegoColor(14,  "Yellow",                 (0xF2, 0xCD, 0x37), "common"),
    LegoColor(226, "Bright Light Yellow",    (0xFF, 0xF0, 0x3A), "common"),
    LegoColor(191, "Bright Light Orange",    (0xF8, 0xBB, 0x3D), "common"),
    LegoColor(25,  "Orange",                 (0xFE, 0x8A, 0x18), "common"),
    LegoColor(484, "Dark Orange",            (0xA9, 0x55, 0x00), "common"),
    LegoColor(462, "Medium Orange",          (0xFF, 0xA7, 0x0B), "extended"),
    LegoColor(125, "Light Orange",           (0xF9, 0xBA, 0x61), "extended"),
    LegoColor(18,  "Light Yellow",           (0xFB, 0xE6, 0x96), "extended"),

    # --- browns / skin tones --------------------------------------------
    LegoColor(19,  "Tan",                    (0xE4, 0xCD, 0x9E), "common"),
    LegoColor(28,  "Dark Tan",               (0x95, 0x8A, 0x73), "common"),
    LegoColor(92,  "Nougat",                 (0xD0, 0x91, 0x68), "common"),
    LegoColor(84,  "Medium Nougat",          (0xCC, 0x70, 0x2A), "common"),
    LegoColor(68,  "Very Light Orange",      (0xF3, 0xCF, 0x9B), "extended"),
    LegoColor(70,  "Reddish Brown",          (0x58, 0x2A, 0x12), "common"),
    LegoColor(308, "Dark Brown",             (0x35, 0x21, 0x00), "common"),
    LegoColor(86,  "Light Brown",            (0x7C, 0x50, 0x3A), "extended"),
    LegoColor(335, "Sand Red",               (0xD6, 0x75, 0x72), "extended"),
)

BY_ID = {c.id: c for c in COLORS}
BY_NAME = {c.name.lower(): c for c in COLORS}

GRAYSCALE_IDS = (15, 151, 71, 72, 0)
BW_IDS = (15, 0)


def get_palette(name: str = "common", extra_ids=(), exclude_ids=()) -> tuple:
    """Return a tuple of LegoColor for a named palette.

    name: "common", "extended"/"all", "grayscale", "bw", or a comma separated
    list of colour ids or colour names.
    """
    key = (name or "common").strip().lower()
    if key in ("common", "default"):
        pal = [c for c in COLORS if c.tier == "common"]
    elif key in ("extended", "all", "full"):
        pal = list(COLORS)
    elif key in ("grayscale", "greyscale", "gray", "grey"):
        pal = [BY_ID[i] for i in GRAYSCALE_IDS]
    elif key in ("bw", "mono", "blackwhite"):
        pal = [BY_ID[i] for i in BW_IDS]
    else:
        pal = []
        for token in key.split(","):
            token = token.strip()
            if not token:
                continue
            if token.isdigit() and int(token) in BY_ID:
                pal.append(BY_ID[int(token)])
            elif token in BY_NAME:
                pal.append(BY_NAME[token])
            else:
                raise ValueError("unknown LEGO colour: %r" % token)

    for cid in extra_ids:
        if cid in BY_ID and BY_ID[cid] not in pal:
            pal.append(BY_ID[cid])
    excl = set(exclude_ids)
    pal = [c for c in pal if c.id not in excl]
    if not pal:
        raise ValueError("palette is empty")
    # stable de-duplication
    seen, out = set(), []
    for c in pal:
        if c.id not in seen:
            seen.add(c.id)
            out.append(c)
    return tuple(out)


# --------------------------------------------------------------------------
# Colour science: sRGB -> CIE L*a*b*, and CIEDE2000 colour difference
# --------------------------------------------------------------------------

_M_RGB2XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
])

# The D65 white point taken from the matrix itself (rather than the rounded
# 95.047/100/108.883 literals), so that pure white lands exactly on L*=100,
# a*=b*=0 instead of a few units of 1e-5 away.
_D65 = _M_RGB2XYZ.sum(axis=1) * 100.0


def srgb_to_lab(rgb) -> np.ndarray:
    """sRGB (0-255, any leading shape) -> CIE L*a*b* under D65."""
    arr = np.asarray(rgb, dtype=np.float64) / 255.0
    arr = np.clip(arr, 0.0, 1.0)
    lin = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M_RGB2XYZ.T * 100.0
    t = xyz / _D65
    eps = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    f = np.where(t > eps, np.cbrt(t), (kappa * t + 16.0) / 116.0)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)], axis=-1)


def delta_e_2000(lab1, lab2, kL=1.0, kC=1.0, kH=1.0) -> np.ndarray:
    """CIEDE2000 colour difference.  Inputs broadcast on the leading axes."""
    lab1 = np.asarray(lab1, dtype=np.float64)
    lab2 = np.asarray(lab2, dtype=np.float64)
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]

    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cbar = 0.5 * (C1 + C2)
    Cbar7 = Cbar ** 7
    G = 0.5 * (1.0 - np.sqrt(Cbar7 / (Cbar7 + 25.0 ** 7)))

    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = np.hypot(a1p, b1)
    C2p = np.hypot(a2p, b2)

    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    h1p = np.where((np.abs(a1p) + np.abs(b1)) == 0, 0.0, h1p)
    h2p = np.where((np.abs(a2p) + np.abs(b2)) == 0, 0.0, h2p)

    dLp = L2 - L1
    dCp = C2p - C1p

    Cprod = C1p * C2p
    dh = h2p - h1p
    dhp = np.where(Cprod == 0, 0.0,
                   np.where(dh > 180.0, dh - 360.0,
                            np.where(dh < -180.0, dh + 360.0, dh)))
    dHp = 2.0 * np.sqrt(np.maximum(Cprod, 0.0)) * np.sin(np.radians(dhp) / 2.0)

    Lbarp = 0.5 * (L1 + L2)
    Cbarp = 0.5 * (C1p + C2p)
    hsum = h1p + h2p
    habs = np.abs(h1p - h2p)
    hbarp = np.where(
        Cprod == 0, hsum,
        np.where(habs <= 180.0, 0.5 * hsum,
                 np.where(hsum < 360.0, 0.5 * (hsum + 360.0), 0.5 * (hsum - 360.0))))

    T = (1.0
         - 0.17 * np.cos(np.radians(hbarp - 30.0))
         + 0.24 * np.cos(np.radians(2.0 * hbarp))
         + 0.32 * np.cos(np.radians(3.0 * hbarp + 6.0))
         - 0.20 * np.cos(np.radians(4.0 * hbarp - 63.0)))

    dtheta = 30.0 * np.exp(-(((hbarp - 275.0) / 25.0) ** 2))
    Cbarp7 = Cbarp ** 7
    Rc = 2.0 * np.sqrt(Cbarp7 / (Cbarp7 + 25.0 ** 7))
    Sl = 1.0 + (0.015 * (Lbarp - 50.0) ** 2) / np.sqrt(20.0 + (Lbarp - 50.0) ** 2)
    Sc = 1.0 + 0.045 * Cbarp
    Sh = 1.0 + 0.015 * Cbarp * T
    Rt = -np.sin(np.radians(2.0 * dtheta)) * Rc

    tL = dLp / (kL * Sl)
    tC = dCp / (kC * Sc)
    tH = dHp / (kH * Sh)
    return np.sqrt(tL * tL + tC * tC + tH * tH + Rt * tC * tH)


# --------------------------------------------------------------------------
# Nearest-colour lookup
# --------------------------------------------------------------------------

_LUT_BITS = 6                      # 64 levels per channel
_LUT_N = 1 << _LUT_BITS
_LUT_STEP = 256 // _LUT_N


@lru_cache(maxsize=16)
def _nearest_lut(palette_key: tuple, kL: float = 1.0, kC: float = 1.0) -> np.ndarray:
    """Build a 64x64x64 RGB -> palette-index lookup table using CIEDE2000."""
    pal_rgb = np.array(palette_key, dtype=np.float64)
    pal_lab = srgb_to_lab(pal_rgb)                      # (P, 3)

    centres = (np.arange(_LUT_N) * _LUT_STEP + _LUT_STEP // 2).astype(np.float64)
    grid = np.stack(np.meshgrid(centres, centres, centres, indexing="ij"), axis=-1)
    flat = grid.reshape(-1, 3)
    out = np.empty(flat.shape[0], dtype=np.int16)

    chunk = 8192
    for start in range(0, flat.shape[0], chunk):
        block = flat[start:start + chunk]
        lab = srgb_to_lab(block)                        # (B, 3)
        d = delta_e_2000(lab[:, None, :], pal_lab[None, :, :], kL=kL, kC=kC)
        out[start:start + chunk] = np.argmin(d, axis=1)
    return out.reshape(_LUT_N, _LUT_N, _LUT_N)


def palette_key(palette) -> tuple:
    return tuple(c.rgb for c in palette)


def nearest_index(rgb, palette, kL=1.0, kC=1.0) -> np.ndarray:
    """Nearest palette index for RGB values (0-255, shape (..., 3)).

    kL < 1 makes the matcher care more about getting the brightness right,
    which preserves the shapes in a picture; kC > 1 makes it care less about
    colourfulness, which stops a limited palette from over-saturating.
    """
    lut = _nearest_lut(palette_key(palette), float(kL), float(kC))
    idx = np.clip(np.asarray(rgb), 0, 255).astype(np.int32) >> (8 - _LUT_BITS)
    return lut[idx[..., 0], idx[..., 1], idx[..., 2]].astype(np.int32)


def nearest_index_exact(rgb, palette, kL=1.0, kC=1.0) -> np.ndarray:
    """Exact (un-quantised) nearest palette index -- slower, used in tests."""
    pal_lab = srgb_to_lab(np.array([c.rgb for c in palette], dtype=np.float64))
    lab = srgb_to_lab(np.asarray(rgb, dtype=np.float64))
    d = delta_e_2000(lab[..., None, :], pal_lab, kL=kL, kC=kC)
    return np.argmin(d, axis=-1).astype(np.int32)
