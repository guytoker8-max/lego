"""Purchase orders for suppliers that are not driven by an API.

Most brick suppliers take orders by email, spreadsheet or a web portal, not
by API.  For those, "creating an order" means writing a purchase order a
person can send and track: the lines in the supplier's own part numbers,
where it ships, whether it ships blind, and the booklet to put in the box.
This ledger is where those live, and where the operations screen moves them
along as the supplier replies.

One JSON file per purchase order, the same way ``Store`` keeps everything
else, so it survives a restart and needs no database.
"""

from __future__ import annotations

import csv
import io
import json
import os
import threading
import time
from xml.sax.saxutils import escape

from .base import SUPPLIER_STATUSES
from .colors import bricklink_color


class PurchaseOrderLedger:
    def __init__(self, root: str):
        self.root = os.path.join(os.path.abspath(root), "supplier_orders")
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, reference: str) -> str:
        safe = "".join(ch for ch in reference if ch.isalnum() or ch in "-_")
        return os.path.join(self.root, "%s.json" % safe)

    def save(self, po: dict) -> dict:
        po = dict(po)
        po["updated_at"] = time.time()
        path = self._path(po["reference"])
        with self._lock:
            with open(path + ".tmp", "w") as fh:
                json.dump(po, fh)
            os.replace(path + ".tmp", path)
        return po

    def get(self, reference: str) -> dict | None:
        path = self._path(reference)
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            return json.load(fh)

    def list(self, supplier: str | None = None) -> list:
        out = []
        for name in os.listdir(self.root):
            if name.endswith(".json"):
                po = self.get(name[:-5])
                if po and (supplier is None or po.get("supplier") == supplier):
                    out.append(po)
        out.sort(key=lambda p: -p.get("created_at", 0))
        return out

    def advance(self, reference: str, status: str, *, tracking: dict | None = None,
                note: str = "") -> dict:
        if status not in SUPPLIER_STATUSES:
            raise ValueError("unknown supplier status: %r" % status)
        po = self.get(reference)
        if po is None:
            raise KeyError(reference)
        po["status"] = status
        po.setdefault("history", []).append(
            {"status": status, "at": time.time(), "note": note})
        if tracking:
            po["tracking"] = tracking
        return self.save(po)


def purchase_order_csv(po: dict) -> str:
    """The lines as a spreadsheet a supplier can price and pick from."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["supplier_sku", "design_id", "part", "colour", "colour_id",
                "quantity"])
    for l in po.get("lines", []):
        w.writerow([l.get("supplier_sku", ""), l["part_id"], l["part_name"],
                    l["color_name"], l["color_id"], l["quantity"]])
    return buf.getvalue()


def purchase_order_bricklink_xml(po: dict) -> str:
    """The lines as a BrickLink wanted-list XML.

    It is the one parts-list format every supplier in the research accepts
    (Wobrick, Brickwith and the marketplaces), so it is what gets attached
    to the email or uploaded to the portal.  Colours are BrickLink's; a
    colour with no known mapping is left out of COLOR and named in REMARKS
    so the person sending it can fix it by hand.
    """
    out = ["<INVENTORY>"]
    for l in po.get("lines", []):
        bl = bricklink_color(int(l["color_id"]))
        item = ["<ITEM>", "<ITEMTYPE>P</ITEMTYPE>",
                "<ITEMID>%s</ITEMID>" % escape(str(l["part_id"]))]
        if bl is not None:
            item.append("<COLOR>%d</COLOR>" % bl)
        item.append("<MINQTY>%d</MINQTY>" % int(l["quantity"]))
        remark = l.get("supplier_sku") or ""
        if bl is None:
            remark = ("%s colour: %s (LDraw %s)" % (
                remark, l.get("color_name", ""), l["color_id"])).strip()
        if remark:
            item.append("<REMARKS>%s</REMARKS>" % escape(remark))
        item.append("</ITEM>")
        out.append("".join(item))
    out.append("</INVENTORY>")
    return "\n".join(out) + "\n"
