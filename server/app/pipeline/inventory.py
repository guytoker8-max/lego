"""Stage 7 - PartsInventory.

The bill of materials, derived from the model and from nothing else.

This is deliberate.  If the parts list were assembled from the analysis, or
from the instructions, or from anything but the placed elements themselves,
it could drift from what the model actually contains -- and then the box
arrives missing four pieces.  Counting the model is the only way the list is
guaranteed to match, so that is what happens here, every time, including
after an edit or a repair.
"""

from __future__ import annotations

from collections import Counter

from ..library import LIBRARY, BrickLibrary, color_by_id
from ..models import BomLine, BrickModel


class PartsInventory:
    def __init__(self, library: BrickLibrary = LIBRARY):
        self.library = library

    def bill_of_materials(self, model: BrickModel) -> list:
        """One line per (part, colour), most numerous first."""
        counts = Counter((b.part_id, b.color_id) for b in model.bricks)
        lines = []
        for (part_id, color_id), qty in counts.items():
            brick = self.library.get(part_id)
            color = color_by_id(color_id)
            lines.append(BomLine(
                part_id=part_id,
                part_name=brick.name,
                color_id=color_id,
                color_name=color.name,
                color_hex=color.hex,
                quantity=qty,
                unit_weight_g=brick.weight_g,
                unit_cost=brick.base_cost,
            ))
        lines.sort(key=lambda l: (-l.quantity, l.part_id))
        return lines

    def summary(self, model: BrickModel) -> dict:
        lines = self.bill_of_materials(model)
        return {
            "fingerprint": model.fingerprint(),
            "total_pieces": sum(l.quantity for l in lines),
            "distinct_parts": len({l.part_id for l in lines}),
            "distinct_colors": len({l.color_id for l in lines}),
            "total_weight_g": round(sum(l.line_weight_g for l in lines), 1),
            "lines": [l.to_dict() for l in lines],
        }

    def reconcile(self, model: BrickModel, lines: list) -> list:
        """Prove the list and the model agree.  Returns the disagreements.

        Cheap to run and worth running: it is the check that keeps the
        digital model, the printed booklet and the physical kit identical,
        which the brief calls the most important technical requirement.
        """
        from_model = Counter((b.part_id, b.color_id) for b in model.bricks)
        from_list = Counter()
        for l in lines:
            from_list[(l.part_id, l.color_id)] += l.quantity

        problems = []
        for key in set(from_model) | set(from_list):
            a, b = from_model.get(key, 0), from_list.get(key, 0)
            if a != b:
                problems.append(
                    "%s in colour %d: model has %d, parts list has %d"
                    % (key[0], key[1], a, b))
        return problems

    def check_availability(self, lines: list) -> list:
        """Anything the library cannot supply in the quantity needed."""
        short = []
        for l in lines:
            if not self.library.available(l.part_id, l.quantity):
                short.append({"part_id": l.part_id, "part_name": l.part_name,
                              "color_name": l.color_name,
                              "needed": l.quantity})
        return short
