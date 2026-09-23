"""Suppliers that take a price list and a purchase order.

One entry per company worth wiring up, with what the research established
about it (see docs/SUPPLIER_RESEARCH.md).  Loading a real price list for one
is setting its environment variable to a CSV path; until then it is listed
on the operations screen as "not contracted" and cannot quote.
"""

from .base import Capabilities

PROFILES: tuple = ()
