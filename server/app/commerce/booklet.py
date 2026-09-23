"""The printed instruction booklet that goes in the box.

A PDF drawn from the structured model -- the same bricks, in the same steps,
that the website shows -- so the supplier prints exactly what the customer
approved.  Every page carries the model's fingerprint; if a booklet and a
parts bag ever disagree, the fingerprints say which one is wrong.

Drawn with Pillow alone (isometric, painter's algorithm, as ``preview.py``
does) so the server needs no browser, no GPU and no PDF library.  The pages
are A4 at 150 dpi, which prints cleanly and keeps a 100-page booklet small.
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

from ..library import LIBRARY, PLATE_MM, STUD_MM, color_by_id
from ..models import BrickModel

PAGE = (1240, 1754)                 # A4 @ 150 dpi
MARGIN = 90
INK = (29, 27, 32)
MUTED = (120, 116, 124)
PAPER = (255, 255, 255)
ACCENT = (229, 62, 44)


def _font(size: int, bold: bool = False):
    names = (["DejaVuSans-Bold.ttf", "Arial Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "Arial.ttf"])
    for n in names:
        for d in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts",
                  "/Library/Fonts", ""):
            try:
                return ImageFont.truetype(os.path.join(d, n) if d else n, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


def _mix(rgb, other, t):
    return tuple(int(a * (1 - t) + b * t) for a, b in zip(rgb, other))


def render_model(model: BrickModel, size, *, visible=None, highlight=(),
                 angle: float = 0.75, background=PAPER, fade: float = 0.0):
    """Draw the bricks in ``visible`` (all if None), studs and all.

    Bricks in ``highlight`` are drawn at full strength with a dark outline;
    the rest are faded toward the paper, so a step page shows at a glance
    which pieces are new.
    """
    w_px, h_px = size
    idx = range(len(model.bricks)) if visible is None else visible
    highlight = set(highlight)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def project(x, y, z):
        return (x * cos_a - z * sin_a, (x * sin_a + z * cos_a) * 0.5 - y)

    # Frame on the whole model, not just what is visible yet, so the model
    # does not jump around the page from one step to the next.
    pts = []
    for b in model.bricks:
        br = LIBRARY.get(b.part_id)
        w, d = br.footprint(b.rotation)
        for xx in (b.x, b.x + w):
            for zz in (b.z, b.z + d):
                for yy in (b.y, b.y + br.h + 0.6):
                    pts.append(project(xx * STUD_MM, yy * PLATE_MM, zz * STUD_MM))
    img = Image.new("RGB", size, background)
    if not pts:
        return img
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    span = max(max(xs) - min(xs), (max(ys) - min(ys)) * w_px / h_px) or 1.0
    scale = w_px * 0.9 / span
    ox = w_px / 2 - (min(xs) + max(xs)) / 2 * scale
    oy = h_px / 2 - (min(ys) + max(ys)) / 2 * scale

    def sc(x, y, z):
        X, Y = project(x, y, z)
        return (X * scale + ox, Y * scale + oy)

    items = []
    for i in idx:
        b = model.bricks[i]
        br = LIBRARY.get(b.part_id)
        w, d = br.footprint(b.rotation)
        depth = (b.x + w / 2) + (b.z + d / 2) + (b.y + br.h) * 0.36
        items.append((depth, i, b, br, w, d))
    items.sort(key=lambda t: t[0])

    draw = ImageDraw.Draw(img)
    for _, i, b, br, w, d in items:
        rgb = color_by_id(b.color_id).rgb
        is_new = i in highlight
        if highlight and not is_new:
            rgb = _mix(rgb, background, 0.55 if fade == 0 else fade)
        edge = (20, 20, 24) if is_new else _shade(rgb, 0.5)
        x0, x1 = b.x * STUD_MM, (b.x + w) * STUD_MM
        z0, z1 = b.z * STUD_MM, (b.z + d) * STUD_MM
        y0, y1 = b.y * PLATE_MM, (b.y + br.h) * PLATE_MM
        width = 2 if is_new else 1
        draw.polygon([sc(x0, y1, z0), sc(x1, y1, z0), sc(x1, y1, z1),
                      sc(x0, y1, z1)], fill=_shade(rgb, 1.0), outline=edge,
                     width=width)
        draw.polygon([sc(x0, y0, z1), sc(x1, y0, z1), sc(x1, y1, z1),
                      sc(x0, y1, z1)], fill=_shade(rgb, 0.8), outline=edge,
                     width=width)
        draw.polygon([sc(x1, y0, z0), sc(x1, y0, z1), sc(x1, y1, z1),
                      sc(x1, y1, z0)], fill=_shade(rgb, 0.62), outline=edge,
                     width=width)
        if br.has_studs:
            r = 2.4 * scale
            for dz in range(d):
                for dx in range(w):
                    cx, cy = sc(x0 + (dx + 0.5) * STUD_MM, y1,
                                z0 + (dz + 0.5) * STUD_MM)
                    lift = 1.7 * scale
                    draw.ellipse([cx - r, cy - r * 0.5, cx + r, cy + r * 0.5],
                                 fill=_shade(rgb, 0.72))
                    draw.ellipse([cx - r, cy - lift - r * 0.5, cx + r,
                                  cy - lift + r * 0.5],
                                 fill=_shade(rgb, 1.1), outline=_shade(rgb, 0.6))
    return img


def _part_icon(part_id: str, color_id: int, size: int = 90) -> Image.Image:
    """One element, drawn alone, for the 'add these' strip and parts pages."""
    from ..models import PlacedBrick
    probe = BrickModel(name="", bricks=[PlacedBrick(part_id, color_id, 0, 0, 0, 0)])
    return render_model(probe, (size, size), background=PAPER)


def _footer(draw, model, page_no):
    f = _font(20)
    draw.text((MARGIN, PAGE[1] - 60),
              "%s  ·  model %s" % (model.name, model.fingerprint()),
              fill=MUTED, font=f)
    draw.text((PAGE[0] - MARGIN, PAGE[1] - 60), str(page_no), fill=MUTED,
              font=f, anchor="ra")


def build_booklet(model: BrickModel, describe: list, parts: dict,
                  brand: str = "BrickSnap",
                  disclaimer: str = "") -> list:
    """The booklet as a list of page images, cover first."""
    pages = []

    # ---- cover -------------------------------------------------------
    cover = Image.new("RGB", PAGE, PAPER)
    d = ImageDraw.Draw(cover)
    d.text((MARGIN, MARGIN), brand.upper(), fill=ACCENT, font=_font(34, True))
    d.text((MARGIN, MARGIN + 70), model.name, fill=INK, font=_font(76, True))
    w, h, dd = model.dimensions_cm
    d.text((MARGIN, MARGIN + 170),
           "%d pieces  ·  %g × %g × %g cm  ·  %d steps"
           % (model.piece_count, w, dd, h, len(model.steps)),
           fill=MUTED, font=_font(30))
    hero = render_model(model, (PAGE[0] - 2 * MARGIN, 1150))
    cover.paste(hero, (MARGIN, 330))
    if disclaimer:
        d.text((MARGIN, PAGE[1] - 130), disclaimer[:150], fill=MUTED,
               font=_font(18))
    _footer(d, model, 1)
    pages.append(cover)

    # ---- parts -------------------------------------------------------
    lines = parts.get("lines", [])
    per_page, cols = 30, 5
    cell_w = (PAGE[0] - 2 * MARGIN) // cols
    for start in range(0, len(lines), per_page):
        page = Image.new("RGB", PAGE, PAPER)
        d = ImageDraw.Draw(page)
        d.text((MARGIN, MARGIN), "Parts in this set", fill=INK,
               font=_font(48, True))
        d.text((MARGIN, MARGIN + 66), "%d pieces in %d kinds"
               % (parts.get("total_pieces", 0), len(lines)),
               fill=MUTED, font=_font(26))
        for k, l in enumerate(lines[start:start + per_page]):
            cx = MARGIN + (k % cols) * cell_w
            cy = MARGIN + 150 + (k // cols) * 235
            page.paste(_part_icon(l["part_id"], l["color_id"], 150),
                       (cx + (cell_w - 150) // 2, cy))
            d.text((cx + cell_w // 2, cy + 160), "%d×" % l["quantity"],
                   fill=INK, font=_font(30, True), anchor="ma")
            d.text((cx + cell_w // 2, cy + 198),
                   "%s %s" % (l["color_name"], l["part_name"].split(" ")[-1]),
                   fill=MUTED, font=_font(17), anchor="ma")
        _footer(d, model, len(pages) + 1)
        pages.append(page)

    # ---- steps: two to a page ----------------------------------------
    placed = []
    half = (PAGE[1] - 2 * MARGIN - 40) // 2
    page = None
    for n, step in enumerate(describe):
        new = [p["brick_index"] for p in step["placements"]]
        placed.extend(new)
        slot = n % 2
        if slot == 0:
            page = Image.new("RGB", PAGE, PAPER)
            pages.append(page)
        d = ImageDraw.Draw(page)
        top = MARGIN + slot * (half + 40)
        d.text((MARGIN, top), str(step["index"]), fill=INK,
               font=_font(72, True))
        # what to add, as pictures with counts
        x = MARGIN + 150
        for a in step["add"][:7]:
            page.paste(_part_icon(a["part_id"], a["color_id"], 96), (x, top))
            d.text((x + 48, top + 100), "%d×" % a["quantity"], fill=INK,
                   font=_font(24, True), anchor="ma")
            x += 130
        img = render_model(model, (PAGE[0] - 2 * MARGIN, half - 150),
                           visible=list(placed), highlight=new)
        page.paste(img, (MARGIN, top + 140))
        if slot == 1 or n == len(describe) - 1:
            _footer(d, model, len(pages))
    return pages


def booklet_pdf(model: BrickModel, describe: list, parts: dict, path: str,
                **kw) -> str:
    """Write the booklet to ``path`` (cached by the caller on fingerprint)."""
    pages = build_booklet(model, describe, parts, **kw)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    pages[0].save(tmp, "PDF", resolution=150.0, save_all=True,
                  append_images=pages[1:])
    os.replace(tmp, path)
    return path
