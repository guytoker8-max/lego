# The homepage examples

Five pictures, run through the same pipeline a customer's photo goes through,
saved as fixtures in `server/app/examples/data/` and installed into the store
at start-up. `cd server && python scripts/make_examples.py` rebuilds them.

Piece counts before and after the colour work of 2026-09-23 (majority
downsampling, background-aware colour trust, adaptive background threshold):

| Example | Before | After |
|---|---:|---:|
| Golden Retriever | 882 | 697 |
| Red Hatchback | 740 | 433 |
| Family Home | 609 | 715 |
| Portrait Figure | 530 | 401 |
| Potted Cactus | 572 | 850 |

They move in both directions, and that is the expected shape of it. The piece
count is not being minimised — it is capped by the size preset, 900 for the
medium these are built at. What changed is that colour regions are no longer
broken up by seam colours invented between two real ones, so a region that
used to fragment now tiles into larger bricks (the car, the dog), while a
subject whose detail used to be averaged away now survives and costs pieces to
express (the house's windows, the cactus's arms). Both are the pipeline
spending its budget on the picture instead of on noise.

The honest measure is not the count but what the count buys: the retriever was
eleven colours, four of them seam artefacts, and read as a brown blob. It is
now a recognisable sitting dog.
