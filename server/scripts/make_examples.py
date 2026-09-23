"""Rebuild the homepage examples from their source pictures.

    cd server && python scripts/make_examples.py

Each picture goes through exactly the pipeline a customer's photo does --
analysis with the category the customer would pick, the same size preset,
validation, instructions -- and the result is saved as a fixture beside the
picture.  Nothing is hand-edited afterwards.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.runner import BuildPipeline  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "app", "examples", "data")

EXAMPLES = [
    ("pet", "Golden Retriever", "pet", "standard",
     "A sitting dog, rebuilt with its ears, collar and paws."),
    ("car", "Red Hatchback", "vehicle", "standard",
     "A side view, given depth as a vehicle."),
    ("house", "Family Home", "building", "standard",
     "Walls, roof, chimney and windows, square to the grid."),
    ("person", "Portrait Figure", "person", "standard",
     "A standing figure in a yellow top."),
    ("object", "Potted Cactus", "object", "standard",
     "A cactus in a terracotta pot, flower and all."),
]
SIZES = {"mini": {"size": "mini", "detail": "simple"},
         "standard": {"size": "medium", "detail": "balanced"},
         "detailed": {"size": "large", "detail": "detailed"}}


def main(only=None):
    pipeline = BuildPipeline(api_key=None)
    for slug, title, category, size, caption in EXAMPLES:
        if only and slug not in only:
            continue
        t = time.time()
        src = os.path.join(DATA, "%s.png" % slug)
        analysis, views = pipeline.analyze([src], None, category)
        analysis.display_name = title
        answers = dict(SIZES[size], priority="balanced", unseen_back="yes",
                       category=category)
        result = pipeline.build(views, analysis, answers)
        record = {"title": title, "caption": caption, "category": category,
                  "size": size, "model": result["model"],
                  "summary": result["summary"]}
        with open(os.path.join(DATA, "%s.json" % slug), "w") as fh:
            json.dump(record, fh, separators=(",", ":"))
        s = result["summary"]
        print("%-7s %5d pieces  %s cm  %.1fs" % (
            slug, s["piece_count"], s["dimensions_cm"], time.time() - t))


if __name__ == "__main__":
    main(sys.argv[1:])
