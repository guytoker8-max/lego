"""Colour numbering across suppliers.

Our colour ids are LDraw's (the numbering the palette in ``library/colors``
uses).  BrickLink, and every seller who lists through it, numbers colours
differently -- White is 15 to us and 1 to them -- so an order sent without
translating would ask for the wrong colours in every line.

The table covers the common palette the generator draws from.  It follows
BrickLink's published colour guide; check it against a first real order
before trusting it with a large one.
"""

LDRAW_TO_BRICKLINK = {
    15: 1,     # White
    151: 99,   # Very Light Bluish Gray
    71: 86,    # Light Bluish Gray
    72: 85,    # Dark Bluish Gray
    0: 11,     # Black
    4: 5,      # Red
    320: 59,   # Dark Red
    29: 104,   # Bright Pink
    26: 71,    # Magenta
    30: 157,   # Medium Lavender
    31: 154,   # Lavender
    85: 89,    # Dark Purple
    1: 7,      # Blue
    272: 63,   # Dark Blue
    73: 42,    # Medium Blue
    212: 105,  # Bright Light Blue
    321: 153,  # Dark Azure
    322: 156,  # Medium Azure
    379: 55,   # Sand Blue
    3: 39,     # Dark Turquoise
    323: 152,  # Light Aqua
    2: 6,      # Green
    288: 80,   # Dark Green
    10: 36,    # Bright Green
    27: 34,    # Lime
    330: 155,  # Olive Green
    378: 48,   # Sand Green
    14: 3,     # Yellow
    226: 103,  # Bright Light Yellow
    191: 110,  # Bright Light Orange
    25: 4,     # Orange
    484: 68,   # Dark Orange
    19: 2,     # Tan
    28: 69,    # Dark Tan
    92: 28,    # Nougat
    84: 150,   # Medium Nougat
    70: 88,    # Reddish Brown
    308: 120,  # Dark Brown
}


def bricklink_color(ldraw_id: int) -> int | None:
    return LDRAW_TO_BRICKLINK.get(ldraw_id)
