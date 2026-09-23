"""The supplier-independent brick catalogue.

``library/bricks.py`` says what an element *is* (its size, its studs, its
weight).  This module says what it is *as a product*: the colours it comes
in, what each supplier calls it and charges for it, whether it is in stock,
what we would sell it for, and how it ships.  Every field the business needs
to reason about a part is here, and every one is derived -- from the library,
the colour table and the configured supplier adapters -- rather than typed in
a second time, so the catalogue cannot disagree with what the generator uses.

Part ids come in two forms.  ``part_id`` is the internal, readable id
(``brick_2x4``); ``design_id`` is the industry number (``3001``) that the
model, the parts list and BrickLink-style suppliers all use.  Colour ids are
LDraw's; ``suppliers/colors.py`` translates for suppliers that differ.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .library import LIBRARY, PLATE_MM, STUD_MM, Brick, color_by_id
from .library.colors import COMMON
from .pipeline.pricing import DEFAULT_MARGIN, VAT_RATE

# Colours a baseplate is actually moulded in.  Every other element uses the
# common palette the generator draws from.
BASEPLATE_COLORS = (2, 71, 15, 19, 1, 0)

HS_CODE = "9503.00"          # toys: construction sets and parts


def internal_id(b: Brick) -> str:
    return "%s_%dx%d" % (b.kind, min(b.w, b.d), max(b.w, b.d))


def connection_geometry(b: Brick) -> dict:
    """How the element joins others: studs on top, sockets underneath.

    A 2-wide element grips with tubes between its sockets, a 1-wide one with
    a thin pin; a tile has no studs, so nothing may be placed on it.  The
    validator reasons with exactly this: clutch needs a stud under a socket.
    """
    w, d = min(b.w, b.d), max(b.w, b.d)
    if w >= 2:
        underside = {"type": "tubes", "count": (w - 1) * (d - 1)}
    elif d >= 2:
        underside = {"type": "pins", "count": d - 1}
    else:
        underside = {"type": "open", "count": 0}
    return {
        "grid_mm": STUD_MM,
        "top": {"type": "studs" if b.has_studs else "smooth",
                "count": b.studs if b.has_studs else 0,
                "layout": [b.w, b.d]},
        "bottom": {"type": "sockets", "count": b.studs, "layout": [b.w, b.d],
                   "grip": underside},
        "stackable_on_top": b.has_studs,
    }


@dataclass
class CatalogPart:
    part_id: str
    design_id: str
    name: str
    type: str
    width: int                  # studs
    length: int                 # studs
    height: int                 # plate units (a brick is 3)
    size_mm: list
    connection: dict
    weight_g: float
    available_colors: list
    supplier: str               # the supplier orders currently go to
    supplier_part_id: str
    sku: str
    cost: float                 # supplier cost per element, ILS
    retail_price: float         # what one would sell for loose, incl. VAT
    currency: str
    available: bool
    image: str
    shipping: dict
    offers: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def retail_from_cost(cost: float, margin: float = DEFAULT_MARGIN,
                     vat: float = VAT_RATE) -> float:
    """A single element's shelf price: the set's own margin and VAT."""
    return round(cost / (1.0 - margin) * (1.0 + vat), 2)


class Catalog:
    def __init__(self, supplier_key: str = "compatible"):
        self.supplier_key = supplier_key

    def _adapter(self):
        from .suppliers import get_adapter
        return get_adapter(self.supplier_key)

    def colors_for(self, b: Brick) -> list:
        ids = BASEPLATE_COLORS if b.kind == "baseplate" else [c.id for c in COMMON]
        return [{"color_id": cid, "name": color_by_id(cid).name,
                 "hex": color_by_id(cid).hex} for cid in ids]

    def part(self, key: str, color_id: int | None = None) -> CatalogPart:
        b = self._resolve(key)
        adapter = self._adapter()
        colors = self.colors_for(b)
        cid = color_id if color_id is not None else colors[0]["color_id"]
        offer = None
        try:
            offer = adapter.get_product_details(b.part_id, cid)
        except Exception:
            offer = None
        cost = offer.unit_cost if offer else b.base_cost
        w, h, d = b.size_mm()
        return CatalogPart(
            part_id=internal_id(b), design_id=b.part_id, name=b.name,
            type=b.kind, width=min(b.w, b.d), length=max(b.w, b.d),
            height=b.h, size_mm=[w, round(h, 1), d],
            connection=connection_geometry(b), weight_g=b.weight_g,
            available_colors=colors, supplier=adapter.key,
            supplier_part_id=offer.supplier_sku if offer else b.part_id,
            sku="BS-%s-%d" % (b.part_id, cid), cost=round(cost, 4),
            retail_price=retail_from_cost(cost), currency="ILS",
            available=bool(LIBRARY.available(b.part_id)),
            image="/api/catalog/parts/%s/image.svg?color=%d" % (b.part_id, cid),
            shipping={"unit_weight_g": b.weight_g, "packaging": "polybag by colour",
                      "hs_code": HS_CODE,
                      "lead_time_days": adapter.capabilities.lead_time_days,
                      "ships_from": list(adapter.capabilities.regions)},
            offers=[o.to_dict() for o in [offer] if o],
        )

    def parts(self) -> list:
        return [self.part(b.part_id) for b in LIBRARY.all()]

    @staticmethod
    def _resolve(key: str) -> Brick:
        if LIBRARY.exists(key):
            return LIBRARY.get(key)
        for b in LIBRARY.all():
            if internal_id(b) == key:
                return b
        return LIBRARY.get(key)             # raises UnknownPartError


def part_svg(b: Brick, hex_color: str, size: int = 160) -> str:
    """A small isometric drawing of the element, for the parts list.

    Drawn from the element's own dimensions, so a 2x4 looks like a 2x4 and a
    tile has no studs; no image files to keep in step with the library.
    """
    import math
    w, d = b.w, b.d
    h = b.h * PLATE_MM / STUD_MM                    # height in stud units
    a = math.radians(30)
    cx, cy = math.cos(a), math.sin(a)

    def p(x, y, z):
        return ((x - z) * cx, (x + z) * cy - y)

    corners = [p(x, y, z) for x in (0, w) for z in (0, d) for y in (0, h + 0.3)]
    minx = min(c[0] for c in corners); maxx = max(c[0] for c in corners)
    miny = min(c[1] for c in corners); maxy = max(c[1] for c in corners)
    span = max(maxx - minx, maxy - miny)
    s = size * 0.84 / span
    ox = size / 2 - (minx + maxx) / 2 * s
    oy = size / 2 - (miny + maxy) / 2 * s

    def pt(x, y, z):
        X, Y = p(x, y, z)
        return "%.1f,%.1f" % (X * s + ox, Y * s + oy)

    def shade(f):
        r, g, bl = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(min(255, int(c * f)) for c in (r, g, bl))

    edge = shade(0.55)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
           'width="%d" height="%d">' % (size, size, size, size)]
    poly = '<polygon points="%s" fill="%s" stroke="%s" stroke-width="1" ' \
           'stroke-linejoin="round"/>'
    out.append(poly % (" ".join([pt(0, 0, d), pt(w, 0, d), pt(w, h, d),
                                 pt(0, h, d)]), shade(0.82), edge))
    out.append(poly % (" ".join([pt(w, 0, 0), pt(w, 0, d), pt(w, h, d),
                                 pt(w, h, 0)]), shade(0.66), edge))
    out.append(poly % (" ".join([pt(0, h, 0), pt(w, h, 0), pt(w, h, d),
                                 pt(0, h, d)]), shade(1.0), edge))
    if b.has_studs:
        r = 0.3 * s
        for z in range(d):
            for x in range(w):
                X, Y = p(x + 0.5, h, z + 0.5)
                X, Y = X * s + ox, Y * s + oy
                sh = 0.17 * s
                out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" '
                           'fill="%s"/>' % (X, Y, r, r * 0.58, shade(0.7)))
                out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                           'fill="%s"/>' % (X - r, Y - sh, 2 * r, sh, shade(0.7)))
                out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" '
                           'fill="%s" stroke="%s" stroke-width="0.8"/>'
                           % (X, Y - sh, r, r * 0.58, shade(1.08), edge))
    out.append("</svg>")
    return "".join(out)
