# BrickSnap

Turn a photo into a brick set you can actually build.

Upload a picture. The app works out what it is, reconstructs it in three
dimensions, fills that shape with real LEGO-compatible elements, proves the
result can be assembled, and hands back a 3D model, a parts list, step-by-step
instructions and a price — all describing the same object.

> BrickSnap is not affiliated with, authorised by or endorsed by The LEGO
> Group. Sets are built from LEGO-compatible elements. The exact wording is
> configurable in `server/app/config.py` and is served to the app, so it can
> be changed in one place.

## Running it

Two processes: a Python API and an Expo app.

```bash
# API
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# app, in another terminal
cd app
npm install
npx expo start
```

The app reads the API's address from `extra.apiUrl` in `app/app.json`. On a
physical device, change `127.0.0.1` to your machine's LAN address.

Subject recognition uses Claude vision when `ANTHROPIC_API_KEY` is set in the
API's environment. **The key is read server side and never sent to the app.**
Without it everything still works: the analysis falls back to computer vision,
and you get a correct model with a generic name and a conservative depth.

```bash
export ANTHROPIC_API_KEY=sk-...        # optional
export BRICKSNAP_DATA=./data           # where models and orders are kept
export BRICKSNAP_SUPPLIER=compatible   # which supplier to quote against
```

## How a photo becomes a set

Each stage is a separate module. None of them is a prompt: the vision model
names the subject and judges its depth, and everything after that is geometry
and arithmetic, which is what makes the result repeatable and the parts list
something you can actually put in a box.

| Stage | Module | What it does |
|---|---|---|
| Reference analysis | `pipeline/reference_analyzer.py` | Segments the subject, measures it, names it, and decides what to ask the user |
| Geometry | `pipeline/geometry.py` | Silhouettes → a filled volume on the stud grid |
| Optimisation | `pipeline/optimizer.py` | Hollows it, calms the colours, props overhangs |
| Brick conversion | `pipeline/brick_generator.py` | Volume → real elements, real colours, staggered seams |
| Validation | `pipeline/validator.py` | Proves it can be built; repairs it until it can |
| Instructions | `pipeline/instructions.py` | A booklet whose every step rests on the last |
| Parts | `pipeline/inventory.py` | The bill of materials, counted from the model |
| Pricing | `pipeline/pricing.py` | A price traced to that bill |
| Orders | `pipeline/orders.py` | The kit, through whichever supplier is configured |

Two libraries sit underneath: `library/bricks.py` is the only source of
parts, and `library/colors.py` the only source of colours. Nothing may invent
either. `library/suppliers.py` is the abstraction that keeps fulfilment from
being wired into the app.

### The geometry, specifically

A photo shows one side of a thing, so the third dimension has to come from
somewhere:

- **Two or more photos** give it honestly. A cell is solid only where it is
  inside the subject in every view that can see it — a visual hull, the same
  carving a turntable scanner does with two silhouettes instead of two hundred.
- **One photo** cannot, so the app asks before interpreting. The silhouette is
  extruded with a depth profile: how far a point stands proud depends on how
  far it is from the outline, which is what makes a face read as a face rather
  than a cardboard cut-out.

Coordinates: `x` and `z` are studs (8 mm); `y` is counted in plate units
(3.2 mm) so plates and bricks share one grid. A standard brick is three.

### What "buildable" means here

The validator is the gate — nothing reaches a screen until it passes:

1. Every element is one the library stocks.
2. No two share a cell; nothing sits below the baseplate.
3. Everything is clutched to something — studs, not mere adjacency.
4. Everything can be reached building *upward* from the baseplate. A piece
   whose only joint is to something above it is connected once finished but
   could never have been placed, so it counts as unsupported and gets propped.
5. The centre of mass falls over the footprint.
6. Every step can be assembled onto the one before it.

Failures are repaired and re-checked rather than reported, and repairs are
shown to the user.

### One model, three views of it

The digital model, the parts list, the instructions and the physical kit must
be the same object. That is enforced, not hoped for: the structure is hashed
into a fingerprint that the model, parts and steps endpoints all carry, the
instructions screen refuses to open if the two it fetched disagree, and the
order route refuses a set whose list and model do not reconcile.

## Size presets

| Preset | Piece budget | Max dimension | Colours |
|---|---|---|---|
| Mini | 180 | 12 cm | 6 |
| Small | 400 | 16 cm | 8 |
| Medium | 900 | 22 cm | 12 |
| Large | 1800 | 30 cm | 16 |
| Display | 4500 | 42 cm | 20 |

The budget is *measured*, not predicted: the builder lays the bricks, counts
them including any support the validator adds, and shrinks the model until it
fits. "Small" therefore means small.

## Testing

```bash
cd server && python -m pytest tests/ -q     # 28 tests
cd app && npx tsc --noEmit                  # typecheck
```

The suite is weighted toward the promise rather than the plumbing: that models
validate, that no two bricks overlap, that the parts list reconciles exactly,
that every step rests on the last, that presets respect their budgets, that
prices add up, and that bad input — a text file, a blank frame, a blurry photo,
two objects, a subject too small to resolve — fails in a way a person can act on.

## What is built, and what is not

Phases 1 and 2 of the brief are complete and working end to end: upload,
analysis, questions, a structured brick model, 3D preview, physical validation,
instructions and the parts list.

Phases 3 and 4 have their seams in place but are not finished:

- **No accounts.** Models are stored per install, in `Store`, which is the
  only class that touches the disk — swapping it for Postgres is one class.
- **No model editing yet.** "Make it bigger", "use fewer pieces" would re-run
  the pipeline with changed answers against the same references; the pipeline
  already takes them as parameters.
- **Payment is not connected.** `PaymentProvider` is an interface with a
  deferred stub behind it. No card detail is accepted anywhere in the app.
- **Fulfilment is not contracted.** Of the three supplier routes, only
  LEGO-compatible third-party bricks is wired up; the other two raise
  `SupplierNotConfigured` rather than pretending.

## Known limitations

- **Single studs dominate the piece mix** — roughly 60–70% on a photographic
  subject. A photo reduced to a stud grid leaves short colour runs along every
  boundary, and a short run is bought as 1x1s. The palette reduction, the
  despeckler and the run merger cut this a long way from where it started, but
  it remains the clearest thing left to improve: it drives both cost and build
  time.
- **Depth from a single photo is an interpretation**, and the app says so
  rather than implying a scan.
- **`query-string` is pinned directly** in `app/package.json`. `expo-router`
  4.0.22 imports it without declaring it, so the bundle will not build without.
