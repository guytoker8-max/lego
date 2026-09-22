"""Draw the mosaic: finished previews, the plate plan, and step pictures."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _mix(rgb, other, t):
    return tuple(int(round(rgb[i] * (1 - t) + other[i] * t)) for i in range(3))


def _lighten(rgb, t):
    return _mix(rgb, (255, 255, 255), t)


def _darken(rgb, t):
    return _mix(rgb, (0, 0, 0), t)


def render_mosaic(indices, palette, placements=None, *, stud_px=16, seams=True,
                  highlight=None, dim_unhighlighted=False, full=None,
                  region=None, labels=False, supersample=2,
                  plate_bg=(38, 40, 44), accent=(255, 59, 48)):
    """Render the mosaic (or one panel of it) as a PIL image.

    placements  when given, plate outlines are drawn from the real part layout
    highlight   a set of Placement objects to ring in ``accent``
    full        a set of plates to draw at full colour; everything else is
                faded to a ghost of the finished picture (step pictures)
    dim_unhighlighted  shorthand for ``full=highlight``
    region      (col, row, w, h) to render a single panel
    labels      draw stud rulers along the top and left edges
    """
    indices = np.asarray(indices)
    h, w = indices.shape
    if region is None:
        region = (0, 0, w, h)
    rc, rr, rw, rh = region

    S = max(1, int(supersample))
    u = stud_px * S                                  # one stud, in work pixels
    pad = int(round(0.35 * u))
    ruler = int(round(1.7 * u)) if labels else 0

    W = rw * u + 2 * pad + ruler
    H = rh * u + 2 * pad + ruler
    img = Image.new("RGB", (W, H), _darken(plate_bg, 0.45))
    d = ImageDraw.Draw(img)

    ox, oy = ruler + pad, ruler + pad
    d.rectangle([ox - pad, oy - pad, ox + rw * u + pad - 1, oy + rh * u + pad - 1],
                fill=plate_bg)

    highlight = set(highlight or ())
    if placements is None:
        placements = [_ImplicitPlate(c, r, int(indices[r, c]))
                      for r in range(rr, rr + rh) for c in range(rc, rc + rw)]
        seams = False

    for p in placements:
        if not (rc <= p.col < rc + rw and rr <= p.row < rr + rh):
            continue
        base = palette[p.color_index].rgb
        if full is not None:
            hot = p in full
        else:
            hot = (not dim_unhighlighted) or (p in highlight)
        if not hot:
            base = _mix(base, plate_bg, 0.72)

        x0 = ox + (p.col - rc) * u
        y0 = oy + (p.row - rr) * u
        x1 = x0 + p.w * u
        y1 = y0 + p.h * u

        # the plate surface sits a touch darker so that the lit stud tops
        # average back to the true brick colour
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=_darken(base, 0.07))
        if seams:
            edge = _darken(base, 0.35 if hot else 0.15)
            d.rectangle([x0, y0, x1 - 1, y1 - 1], outline=edge,
                        width=max(1, S // 2))

        # studs -- a soft shadow, the stud top, and a small specular cap
        rad = 0.29 * u
        shadow = _darken(base, 0.26)
        top = base
        cap = _lighten(base, 0.14) if sum(base) < 690 else _lighten(base, 0.05)
        for sy in range(p.h):
            for sx in range(p.w):
                cx = x0 + (sx + 0.5) * u
                cy = y0 + (sy + 0.5) * u
                d.ellipse([cx - rad, cy - rad + 0.07 * u,
                           cx + rad, cy + rad + 0.07 * u], fill=shadow)
                d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=top)
                d.ellipse([cx - rad * 0.60, cy - rad * 0.70,
                           cx + rad * 0.60, cy + rad * 0.30], fill=cap)

    for p in highlight:
        if not (rc <= p.col < rc + rw and rr <= p.row < rr + rh):
            continue
        x0 = ox + (p.col - rc) * u
        y0 = oy + (p.row - rr) * u
        x1 = x0 + p.w * u - 1
        y1 = y0 + p.h * u - 1
        d.rectangle([x0 - S, y0 - S, x1 + S, y1 + S], outline=(255, 255, 255),
                    width=max(2, S))
        d.rectangle([x0, y0, x1, y1], outline=accent, width=max(2, S))

    if labels:
        f = _font(int(0.85 * u))
        tick = _mix(plate_bg, (255, 255, 255), 0.55)
        for c in range(rc, rc + rw):
            n = c + 1
            if n == 1 or n % 4 == 0 or c == rc + rw - 1:
                d.text((ox + (c - rc + 0.5) * u, ruler * 0.55), str(n),
                       fill=tick, font=f, anchor="mm")
        for r in range(rr, rr + rh):
            n = r + 1
            if n == 1 or n % 4 == 0 or r == rr + rh - 1:
                d.text((ruler * 0.55, oy + (r - rr + 0.5) * u), str(n),
                       fill=tick, font=f, anchor="mm")

    if S > 1:
        img = img.resize((W // S, H // S), Image.LANCZOS)
    return img


class _ImplicitPlate:
    """A bare 1x1 stud, used when no part layout is supplied."""
    __slots__ = ("col", "row", "w", "h", "color_index")

    def __init__(self, col, row, color_index):
        self.col, self.row, self.w, self.h = col, row, 1, 1
        self.color_index = color_index


def side_by_side(original_path, mosaic_img, height=520, gap=18,
                 background=(24, 25, 28)):
    """Original photo next to the brick version, for a quick eyeball check."""
    src = Image.open(original_path).convert("RGB")
    sw = max(1, int(round(src.width * height / src.height)))
    src = src.resize((sw, height), Image.LANCZOS)
    mw = max(1, int(round(mosaic_img.width * height / mosaic_img.height)))
    mos = mosaic_img.resize((mw, height), Image.LANCZOS)
    out = Image.new("RGB", (sw + gap + mw, height), background)
    out.paste(src, (0, 0))
    out.paste(mos, (sw + gap, 0))
    return out


def color_swatches(usage, width=760, row_h=34, background=(24, 25, 28)):
    """A legend strip: every colour used, with its stud count."""
    n = len(usage)
    img = Image.new("RGB", (width, max(1, n) * row_h + 12), background)
    d = ImageDraw.Draw(img)
    f = _font(15)
    for i, row in enumerate(usage):
        y = 6 + i * row_h
        rgb = tuple(int(row["color_hex"][j:j + 2], 16) for j in (1, 3, 5))
        d.rounded_rectangle([10, y + 4, 10 + 46, y + row_h - 6], radius=5,
                            fill=rgb, outline=(90, 92, 96))
        d.text((70, y + row_h // 2), row["color_name"], fill=(235, 236, 240),
               font=f, anchor="lm")
        d.text((width - 14, y + row_h // 2),
               "%d studs  (%.1f%%)" % (row["studs"], 100 * row["share"]),
               fill=(160, 163, 170), font=f, anchor="rm")
    return img
