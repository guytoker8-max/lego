"""A rendered still of a model, drawn on the server.

The app draws models in 3D for itself; this exists for the places a picture
has to travel without a GL context behind it -- the thumbnail in My Sets, a
share image, a printed booklet.

Isometric and painter's algorithm: every brick is a box drawn as three
parallelograms, and drawing them back to front gets the occlusion right
without a depth buffer. That is enough for a still, and it keeps the server
free of a GPU dependency.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..library import LIBRARY, BrickLibrary, color_by_id
from ..models import BrickModel

STUD = 8.0
PLATE = 3.2


def render(model: BrickModel, size: int = 900, angle: float = 0.7,
           background=(243, 240, 234), library: BrickLibrary = LIBRARY,
           upto: int | None = None) -> Image.Image:
    """Draw the model. ``upto`` renders only the first N elements."""
    bricks = model.bricks if upto is None else model.bricks[:upto]
    if not bricks:
        return Image.new("RGB", (size, size), background)

    cos_a, sin_a = np.cos(angle), np.sin(angle)

    def project(x, y, z):
        """World (mm) to screen. Isometric: x and z fan out, y goes up."""
        sx = (x * cos_a - z * sin_a)
        sy = (x * sin_a + z * cos_a) * 0.5 - y
        return sx, sy

    faces = []
    for b in bricks:
        brick = library.get(b.part_id)
        w, d = brick.footprint(b.rotation)
        x0, x1 = b.x * STUD, (b.x + w) * STUD
        z0, z1 = b.z * STUD, (b.z + d) * STUD
        y0, y1 = b.y * PLATE, (b.y + brick.h) * PLATE
        rgb = color_by_id(b.color_id).rgb

        # Depth key: draw far-and-low first so near-and-high paints over it.
        depth = (b.x + w / 2) + (b.z + d / 2) + (b.y + brick.h) * 0.36
        faces.append((depth, x0, x1, y0, y1, z0, z1, rgb))

    faces.sort(key=lambda f: f[0])

    pts = []
    for _, x0, x1, y0, y1, z0, z1, _c in faces:
        for xx in (x0, x1):
            for yy in (y0, y1):
                for zz in (z0, z1):
                    pts.append(project(xx, yy, zz))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    scale = (size * 0.86) / span
    ox = size / 2 - (min(xs) + max(xs)) / 2 * scale
    oy = size / 2 - (min(ys) + max(ys)) / 2 * scale

    def screen(x, y, z):
        sx, sy = project(x, y, z)
        return (sx * scale + ox, sy * scale + oy)

    img = Image.new("RGB", (size, size), background)
    draw = ImageDraw.Draw(img)

    for _, x0, x1, y0, y1, z0, z1, rgb in faces:
        top = _shade(rgb, 1.0)
        left = _shade(rgb, 0.78)
        right = _shade(rgb, 0.60)
        edge = _shade(rgb, 0.46)

        draw.polygon([screen(x0, y1, z0), screen(x1, y1, z0),
                      screen(x1, y1, z1), screen(x0, y1, z1)],
                     fill=top, outline=edge)
        draw.polygon([screen(x0, y0, z1), screen(x1, y0, z1),
                      screen(x1, y1, z1), screen(x0, y1, z1)],
                     fill=left, outline=edge)
        draw.polygon([screen(x1, y0, z0), screen(x1, y0, z1),
                      screen(x1, y1, z1), screen(x1, y1, z0)],
                     fill=right, outline=edge)
    return img


def thumbnail(model: BrickModel, size: int = 320, **kw) -> Image.Image:
    return render(model, size=size * 3, **kw).resize((size, size), Image.LANCZOS)


def _shade(rgb, factor: float) -> tuple:
    return tuple(min(255, int(c * factor)) for c in rgb)
