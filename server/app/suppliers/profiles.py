"""Suppliers that take a price list and a purchase order.

One entry per company worth wiring up, with what the research established
about it (see docs/SUPPLIER_RESEARCH.md, 2026-09-23).  None of them has an
ordering API, so each is a ``PriceListSupplier``: we load the price list the
supplier sends us, it quotes from that, and "placing an order" writes a
purchase order (CSV and BrickLink XML) that a person sends by email or
uploads to the supplier's portal.

Loading a real price list for one is setting its environment variable to a
CSV path; until then it is listed on the operations screen as "not
contracted" and cannot quote.  ``None`` in a capability means the research
could not confirm it either way: ask before relying on it.
"""

from .base import Capabilities

PROFILES: tuple = (
    {
        "key": "wobrick",
        "name": "Wobrick (GoBricks agent)",
        "price_list_env": "BRICKSNAP_PRICELIST_WOBRICK",
        "currency": "USD",
        "fx_env": "BRICKSNAP_FX_USD_ILS",
        "fx_to_ils": 3.7,
        "capabilities": Capabilities(
            api="none", orders_via="email", dropship=True, blind_ship=None,
            prints_booklet=True, moq_pieces=0, regions=("CN", "worldwide"),
            lead_time_days=25, part_numbering="bricklink",
            status="not_contracted",
            notes=("First choice. States dropshipping, private-label "
                   "packaging, custom instruction manuals and no minimum for "
                   "most projects; takes parts lists by email in BrickLink or "
                   "Studio format. Unverified: shipping to Israel, and "
                   "parcels with no prices or supplier branding inside. "
                   "About 10-15 business days to prepare plus 7-15 in "
                   "transit."),
        ),
    },
    {
        "key": "brickwith",
        "name": "Brickwith (GoBricks official shop, formerly Webrick)",
        "price_list_env": "BRICKSNAP_PRICELIST_BRICKWITH",
        "currency": "USD",
        "fx_env": "BRICKSNAP_FX_USD_ILS",
        "fx_to_ils": 3.7,
        "capabilities": Capabilities(
            api="none", orders_via="portal", dropship=None, blind_ship=None,
            prints_booklet=None, moq_pieces=0, regions=("CN", "worldwide"),
            lead_time_days=20, part_numbering="own",
            status="not_contracted",
            notes=("Second GoBricks channel and a price benchmark. No "
                   "minimum, ships within 3 business days, accepts BrickLink "
                   "XML uploads. Dropship, blind shipping and booklet "
                   "inserts are unverified."),
        ),
    },
    {
        "key": "marstoy",
        "name": "Marstoy (GoBricks dropship)",
        "price_list_env": "BRICKSNAP_PRICELIST_MARSTOY",
        "currency": "USD",
        "fx_env": "BRICKSNAP_FX_USD_ILS",
        "fx_to_ils": 3.7,
        "capabilities": Capabilities(
            api="none", orders_via="email", dropship=True, blind_ship=None,
            prints_booklet=None, moq_pieces=None, regions=("CN", "worldwide"),
            lead_time_days=14, part_numbering="own",
            status="not_contracted",
            notes=("Backup dropship route for GoBricks parts, quoted by "
                   "email; PayPal adds 4-6%. Minimum order, blind shipping "
                   "and booklet inserts are unverified."),
        ),
    },
)
