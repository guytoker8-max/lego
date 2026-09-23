"""Small image routines the pipeline needs, in numpy and Pillow only.

Deliberately dependency-light: these run on the API box, and pulling OpenCV
in for a flood fill and a distance transform is not worth the install.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter


def load_rgb(path, max_side: int = 900) -> np.ndarray:
    """Open an image, respect EXIF rotation, cap its size, return RGB uint8."""
    img = Image.open(path)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGB")
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint8)


def sharpness(rgb: np.ndarray) -> float:
    """Variance of a Laplacian: low means the photo is blurry or out of focus."""
    g = rgb.astype(np.float32).mean(axis=2)
    lap = (-4 * g
           + np.roll(g, 1, 0) + np.roll(g, -1, 0)
           + np.roll(g, 1, 1) + np.roll(g, -1, 1))[1:-1, 1:-1]
    return float(lap.var())


def subject_mask(rgb: np.ndarray, tolerance: float | None = None) -> np.ndarray:
    """The subject, as a single region. See ``segment`` for the blob count."""
    return segment(rgb, tolerance)[0]


def segment(rgb: np.ndarray, tolerance: float | None = None) -> tuple:
    """The subject and the blob count.  See ``cut`` for the rest."""
    c = cut(rgb, tolerance)
    return c.mask, c.blobs


def segment_full(rgb: np.ndarray, tolerance: float | None = None) -> tuple:
    """(mask, blobs, background refs, tolerance).  See ``cut`` for the rest."""
    c = cut(rgb, tolerance)
    return c.mask, c.blobs, c.refs, c.tolerance


MIN_SUBJECT = 0.02          # below this the flood ate the subject
MAX_SUBJECT = 0.72          # above this it never found the background
BUSY_TOLERANCE = 28.0       # a background this varied blurs the outline


@dataclass
class Cutout:
    """A subject separated from its background, and how well that went.

    The numbers after the mask are what lets the rest of the pipeline be
    honest with the customer.  A cut can be wrong in ways the mask alone does
    not show, and a set built from a bad cut looks like a lump: better to say
    "the background in this photo is busy" than to hand someone a mug-shaped
    growth on their dog.
    """

    mask: np.ndarray
    blobs: int
    refs: np.ndarray
    tolerance: float
    fallback: bool = False        # the flood failed and the centre cut was used


def cut(rgb: np.ndarray, tolerance: float | None = None) -> Cutout:
    """Separate the subject from its background.

    Photos of a *thing* almost always put the thing in the middle against a
    more uniform surround, so we flood the background inward from the border
    and keep what the flood cannot reach.  Where that fails -- a busy scene,
    a subject that runs off the edge -- we fall back to a centre-weighted
    colour-distance cut, which at least keeps the middle of the frame.
    """
    h, w = rgb.shape[:2]
    lab = _to_lab(rgb)

    # --- border flood -----------------------------------------------------
    border = np.zeros((h, w), dtype=bool)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    seed_colors = lab[border]
    # A handful of representative border colours beats the single mean when
    # the background is, say, grass at the bottom and sky at the top.
    refs = _kmeans(seed_colors, k=3, iters=8)

    dist = np.min(
        np.stack([np.linalg.norm(lab - r, axis=2) for r in refs], axis=0), axis=0
    )
    if tolerance is None:
        tolerance = _background_tolerance(dist[border])
    bg_like = dist < tolerance
    background = _flood_from_border(bg_like)
    mask = ~background

    mask = _close(mask)
    # Count the separate blobs *before* reducing to one, or the count is
    # always one and "there is more than one object here" can never be said.
    blobs = component_count(mask)
    mask = _largest_component(mask)

    # A subject that is nearly the whole frame, or nearly none of it, means the
    # flood went wrong rather than that the photo is unusual: people leave room
    # around the thing they are photographing.  MAX_SUBJECT is set well above
    # any real close-up and well below the coverage a leaking flood produces.
    fallback = False
    coverage = mask.mean()
    if coverage < MIN_SUBJECT or coverage > MAX_SUBJECT:
        fallback = True
        fallen = _close(_centre_cut(lab))
        blobs = component_count(fallen)
        mask = _largest_component(fallen)

    return Cutout(mask=mask, blobs=blobs, refs=refs,
                  tolerance=float(tolerance), fallback=fallback)


def _background_tolerance(border_spread: np.ndarray,
                          low: float = 10.0, high: float = 34.0) -> float:
    """How far from a background colour a pixel may be and still be background.

    A fixed figure has to be loose enough for a background that is not one
    flat colour, and that same looseness eats a mid-grey subject on a white
    sweep -- grey sits about 30 Lab units from white, inside the old fixed 34,
    so heads and stone and steel simply vanished into the background.

    The border shows how uniform the background actually is, so the threshold
    comes from its own spread: a clean sweep gets a tight cut, a busy scene
    keeps the loose one.
    """
    if border_spread.size == 0:
        return high
    spread = float(np.percentile(border_spread, 90))
    return float(min(high, max(low, spread * 2.0 + 6.0)))


def component_count(mask: np.ndarray, min_fraction: float = 0.02) -> int:
    """How many separate blobs of subject there are, ignoring specks.

    More than one usually means the photo holds more than one object, which
    is a thing we ask the user about rather than guess at.
    """
    labels, sizes = _label(mask)
    big = [s for s in sizes.values() if s >= mask.size * min_fraction]
    return len(big)


def dominant_colors(rgb: np.ndarray, mask: np.ndarray, k: int = 6) -> list:
    """The k colours that describe the subject, most common first."""
    pts = rgb[mask]
    if len(pts) == 0:
        return []
    if len(pts) > 20000:
        pts = pts[np.random.default_rng(7).choice(len(pts), 20000, replace=False)]
    lab = _rgb_to_lab_flat(pts.astype(np.float32))
    centers = _kmeans(lab, k=k, iters=12)
    d = np.stack([np.linalg.norm(lab - c, axis=1) for c in centers], axis=0)
    assign = d.argmin(axis=0)
    out = []
    for i in range(len(centers)):
        sel = pts[assign == i]
        if len(sel) == 0:
            continue
        out.append((tuple(int(v) for v in sel.mean(axis=0)), len(sel) / len(pts)))
    out.sort(key=lambda t: -t[1])
    return out


def distance_inside(mask: np.ndarray) -> np.ndarray:
    """Chamfer distance from each subject pixel to the nearest edge.

    Drives the depth profile: the middle of a shape bulges toward the viewer,
    the rim tapers off.
    """
    INF = 1e9
    d = np.where(mask, INF, 0.0).astype(np.float32)
    h, w = d.shape
    # forward pass
    for y in range(h):
        row = d[y]
        prev = d[y - 1] if y > 0 else None
        for_x = row.copy()
        if prev is not None:
            for_x = np.minimum(for_x, prev + 1.0)
            for_x[1:] = np.minimum(for_x[1:], prev[:-1] + 1.4142)
            for_x[:-1] = np.minimum(for_x[:-1], prev[1:] + 1.4142)
        d[y] = for_x
        for x in range(1, w):
            if d[y, x] > d[y, x - 1] + 1.0:
                d[y, x] = d[y, x - 1] + 1.0
    # backward pass
    for y in range(h - 1, -1, -1):
        row = d[y]
        nxt = d[y + 1] if y < h - 1 else None
        back = row.copy()
        if nxt is not None:
            back = np.minimum(back, nxt + 1.0)
            back[1:] = np.minimum(back[1:], nxt[:-1] + 1.4142)
            back[:-1] = np.minimum(back[:-1], nxt[1:] + 1.4142)
        d[y] = back
        for x in range(w - 2, -1, -1):
            if d[y, x] > d[y, x + 1] + 1.0:
                d[y, x] = d[y, x + 1] + 1.0
    d[~mask] = 0.0
    return d


def crop_to_mask(rgb: np.ndarray, mask: np.ndarray, pad: int = 2) -> tuple:
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return rgb, mask
    y0, y1 = max(0, ys.min() - pad), min(mask.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(mask.shape[1], xs.max() + 1 + pad)
    return rgb[y0:y1, x0:x1], mask[y0:y1, x0:x1]


def resize_mask(mask: np.ndarray, w: int, h: int, threshold: float = 0.42) -> np.ndarray:
    """Shrink a mask to a stud grid.  A cell is filled if enough of it was."""
    img = Image.fromarray((mask * 255).astype(np.uint8))
    small = np.asarray(img.resize((w, h), Image.BOX), dtype=np.float32) / 255.0
    return small >= threshold


def resize_rgb(rgb: np.ndarray, w: int, h: int) -> np.ndarray:
    """Shrink a photo to the stud grid by majority, not by average.

    Averaging is right for a photograph and wrong for this. One cell becomes
    one brick in one moulded colour, and a cell that straddles a red panel
    and a grey one averages to a dusty rose that is in neither -- then the
    palette, which only has room for a dozen colours, spends one of them on
    the seam between two others. Taking the colour most of the cell actually
    is keeps every brick a colour the photo really contained.

    Pixels are grouped coarsely to decide the majority, then averaged within
    the winning group, so shading inside a flat area still comes through.
    """
    src = np.asarray(rgb, dtype=np.uint8)
    sh, sw = src.shape[:2]
    if sh == h and sw == w:
        return src.copy()

    rows = np.linspace(0, sh, h + 1).astype(int)
    cols = np.linspace(0, sw, w + 1).astype(int)
    out = np.zeros((h, w, 3), dtype=np.uint8)
    band = (src.astype(np.int32) // 24)
    keys_full = band[:, :, 0] * 1024 + band[:, :, 1] * 32 + band[:, :, 2]

    for r in range(h):
        r0, r1 = rows[r], max(rows[r] + 1, rows[r + 1])
        for c in range(w):
            c0, c1 = cols[c], max(cols[c] + 1, cols[c + 1])
            block = src[r0:r1, c0:c1].reshape(-1, 3)
            keys = keys_full[r0:r1, c0:c1].ravel()
            counts = np.bincount(keys)
            win = counts.argmax()
            out[r, c] = block[keys == win].mean(axis=0).round()
    return out


def erode(mask: np.ndarray, rounds: int = 1) -> np.ndarray:
    """Shrink a mask by one cell per round, treating off-grid as inside.

    Off-grid counts as inside so a subject that runs to the edge of the frame
    does not lose its whole border; only real outline cells are dropped.
    """
    out = mask.copy()
    for _ in range(rounds):
        e = out.copy()
        e[1:, :] &= out[:-1, :]
        e[:-1, :] &= out[1:, :]
        e[:, 1:] &= out[:, :-1]
        e[:, :-1] &= out[:, 1:]
        out = e
    return out


def background_like(rgb: np.ndarray, refs, tolerance: float,
                    factor: float = 1.25, ceiling: float = 18.0) -> np.ndarray:
    """Cells whose colour is mostly the background behind the subject.

    A cell on the outline can be under half subject and still be kept for
    shape, and ``resize_rgb`` then gives it the colour most of it is -- which
    for such a cell is the backdrop. Those cells are trusted for shape only,
    and are repainted from their neighbours.

    The threshold stays near the one segmentation used, deliberately. Widen it
    and it starts eating the subject: a mid grey sits about 30 Lab units from
    a white sweep, so a generous margin quietly turns every grey head, stone
    and steel panel into whatever is next to it.
    """
    if refs is None or len(refs) == 0:
        return np.zeros(rgb.shape[:2], dtype=bool)
    lab = _to_lab(rgb)
    dist = np.min(
        np.stack([np.linalg.norm(lab - r, axis=2) for r in refs], axis=0), axis=0
    )
    return dist < min(ceiling, max(tolerance, tolerance * factor))


def clean_colors(rgb: np.ndarray, trusted: np.ndarray,
                 wanted: np.ndarray) -> np.ndarray:
    """Give every wanted cell a colour that came from inside the subject.

    Two things put background into a model otherwise. A cell on the outline
    is part subject and part whatever was behind it, and since a column of
    the model takes the colour of one cell, a pale rim becomes a pale wall
    the whole way through. And a mask widened by symmetry covers cells the
    camera never saw the subject in at all.

    Callers pass the cells they trust; every other wanted cell takes the
    nearest trusted colour instead of the pixel underneath it.
    """
    inner = trusted
    if not inner.any():
        return rgb

    out = rgb.copy()
    known = inner.copy()
    todo = wanted & ~known

    # A neighbour's colour is copied, never averaged with another's. Averaging
    # a red cell against the grey one beside it makes a dusty pink that is in
    # neither the photo nor the model, and the palette then spends one of its
    # few slots on it.
    while todo.any():
        grew = False
        for shift in ("up", "down", "left", "right"):
            if not todo.any():
                break
            src = np.zeros_like(out)
            has = np.zeros_like(known)
            if shift == "up":
                src[1:, :] = out[:-1, :]; has[1:, :] = known[:-1, :]
            elif shift == "down":
                src[:-1, :] = out[1:, :]; has[:-1, :] = known[1:, :]
            elif shift == "left":
                src[:, 1:] = out[:, :-1]; has[:, 1:] = known[:, :-1]
            else:
                src[:, :-1] = out[:, 1:]; has[:, :-1] = known[:, 1:]
            fill = todo & has
            if not fill.any():
                continue
            out[fill] = src[fill]
            known = known | fill
            todo = todo & ~fill
            grew = True
        if not grew:                       # nothing adjacent left to grow from
            break

    return out


def symmetry_score(mask: np.ndarray) -> float:
    """How closely the silhouette mirrors left to right: 1.0 is perfect."""
    flipped = mask[:, ::-1]
    inter = np.logical_and(mask, flipped).sum()
    union = np.logical_or(mask, flipped).sum()
    return float(inter / union) if union else 0.0


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def _to_lab(rgb: np.ndarray) -> np.ndarray:
    flat = _rgb_to_lab_flat(rgb.reshape(-1, 3).astype(np.float32))
    return flat.reshape(rgb.shape[0], rgb.shape[1], 3)


def _rgb_to_lab_flat(rgb: np.ndarray) -> np.ndarray:
    srgb = rgb / 255.0
    lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
    xyz = lin @ m.T
    white = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    t = xyz / white
    eps = (6 / 29) ** 3
    f = np.where(t > eps, np.cbrt(t), t / (3 * (6 / 29) ** 2) + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def _kmeans(points: np.ndarray, k: int = 3, iters: int = 8) -> np.ndarray:
    pts = points.reshape(-1, points.shape[-1])
    if len(pts) == 0:
        return np.zeros((k, points.shape[-1]), dtype=np.float32)
    k = min(k, len(pts))
    rng = np.random.default_rng(11)
    centers = pts[rng.choice(len(pts), k, replace=False)].astype(np.float32)
    for _ in range(iters):
        d = np.linalg.norm(pts[:, None, :] - centers[None, :, :], axis=2)
        assign = d.argmin(axis=1)
        for i in range(k):
            sel = pts[assign == i]
            if len(sel):
                centers[i] = sel.mean(axis=0)
    return centers


def _flood_from_border(passable: np.ndarray) -> np.ndarray:
    """Everything reachable from the frame edge without leaving ``passable``.

    Which is the same thing as: the connected regions of ``passable`` that
    touch the frame edge.  Labelling answers that in one pass, where growing
    the reached set a pixel at a time costs one pass per pixel of travel.
    """
    labels, _sizes = _label(passable)
    edge = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    touching = np.unique(edge)
    touching = touching[touching > 0]
    if len(touching) == 0:
        return np.zeros_like(passable)
    return np.isin(labels, touching)


def _close(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Fill pinholes and bridge one-pixel gaps: dilate then erode."""
    img = Image.fromarray((mask * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    img = img.filter(ImageFilter.MinFilter(radius * 2 + 1))
    return np.asarray(img, dtype=np.uint8) > 127


def _label(mask: np.ndarray) -> tuple:
    """Connected components, 4-connected.  Returns (labels, {label: size}).

    Row runs rather than pixels: a row of a mask is a handful of intervals,
    and two runs on neighbouring rows are the same component when they
    overlap.  That turns labelling into a short loop over runs instead of one
    pass per pixel of the shape's diameter, which is the difference between
    milliseconds and seconds on a photo-sized mask.
    """
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    if not mask.any():
        return labels, {}

    padded = np.zeros((h, w + 2), dtype=bool)
    padded[:, 1:-1] = mask
    step = np.diff(padded.astype(np.int8), axis=1)
    open_at = np.argwhere(step == 1)          # (row, first column of a run)
    shut_at = np.argwhere(step == -1)         # (row, one past its last column)

    rows = [[] for _ in range(h)]             # run index per row, in order
    starts = open_at[:, 1]
    ends = shut_at[:, 1]
    for i, r in enumerate(open_at[:, 0]):
        rows[r].append(i)

    parent = list(range(len(starts)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(a, b):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for y in range(1, h):
        above, here = rows[y - 1], rows[y]
        i = j = 0
        while i < len(above) and j < len(here):
            a, b = above[i], here[j]
            if starts[a] < ends[b] and starts[b] < ends[a]:
                join(a, b)
            if ends[a] <= ends[b]:
                i += 1
            else:
                j += 1

    names = {}
    sizes = {}
    for y in range(h):
        for i in rows[y]:
            r = root(i)
            name = names.get(r)
            if name is None:
                name = len(names) + 1
                names[r] = name
                sizes[name] = 0
            labels[y, starts[i]:ends[i]] = name
            sizes[name] += int(ends[i] - starts[i])
    return labels, sizes


def _largest_component(mask: np.ndarray) -> np.ndarray:
    labels, sizes = _label(mask)
    if not sizes:
        return mask
    best = max(sizes, key=sizes.get)
    return labels == best


def _centre_cut(lab: np.ndarray) -> np.ndarray:
    """Fallback segmentation: what differs from the frame's border colour."""
    h, w = lab.shape[:2]
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    ref = border.mean(axis=0)
    dist = np.linalg.norm(lab - ref, axis=2)
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2, w / 2
    radial = np.sqrt(((yy - cy) / cy) ** 2 + ((xx - cx) / cx) ** 2)
    score = dist * np.clip(1.4 - radial, 0.05, 1.4)
    return score > max(12.0, np.percentile(score, 62))
