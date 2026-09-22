"""Turn a photograph into a grid of LEGO colours."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from . import palette as pal_mod


@dataclass
class GridResult:
    indices: np.ndarray      # (H, W) int, index into palette
    palette: tuple           # tuple[LegoColor]
    source_rgb: np.ndarray   # (H, W, 3) uint8, the downsampled source
    dither: str


def load_and_fit(path, width_studs=None, height_studs=None, *,
                 crop="fit", brightness=1.0, contrast=1.0, saturation=1.0,
                 sharpen=0.0, resample="lanczos", background=(255, 255, 255)):
    """Open an image and reduce it to a stud grid of source colours.

    crop: "fit"  keep the whole picture, derive the missing dimension from the
                 aspect ratio (default);
          "crop" centre-crop to exactly width x height studs;
          "pad"  letterbox onto ``background``.
    """
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGBA", img.size, tuple(background) + (255,))
        flat.alpha_composite(img)
        img = flat.convert("RGB")
    else:
        img = img.convert("RGB")

    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if sharpen:
        img = ImageEnhance.Sharpness(img).enhance(1.0 + float(sharpen))

    src_w, src_h = img.size
    if width_studs is None and height_studs is None:
        width_studs = 48
    if width_studs is None:
        width_studs = max(1, round(height_studs * src_w / src_h))
    if height_studs is None:
        height_studs = max(1, round(width_studs * src_h / src_w))
    width_studs, height_studs = int(width_studs), int(height_studs)

    filt = {"lanczos": Image.LANCZOS, "box": Image.BOX,
            "bicubic": Image.BICUBIC, "nearest": Image.NEAREST}[resample]

    if crop == "crop":
        img = ImageOps.fit(img, (width_studs, height_studs), method=filt,
                           centering=(0.5, 0.5))
    elif crop == "pad":
        img = ImageOps.pad(img, (width_studs, height_studs), method=filt,
                           color=tuple(background), centering=(0.5, 0.5))
    else:  # "fit"
        img = img.resize((width_studs, height_studs), filt)

    return np.asarray(img, dtype=np.uint8)


def quantize(source_rgb: np.ndarray, palette, dither="auto",
             dither_strength=0.4, lightness_weight=1.5,
             chroma_weight=1.0, despeckle_threshold=6.0) -> GridResult:
    """Map every stud to its nearest real LEGO colour."""
    src = np.asarray(source_rgb, dtype=np.uint8)
    mode = dither
    if mode == "auto":
        h, w = src.shape[:2]
        uniq = np.unique(src.reshape(-1, 3), axis=0).shape[0]
        photographic = uniq > max(24, h * w // 40)
        # Error diffusion only pays off once a stud is small enough that the
        # eye blends neighbours.  Below roughly 80 studs across it just reads
        # as speckle, so a plain nearest-colour match looks far better.
        mode = "floyd" if (photographic and max(h, w) >= 80) else "none"

    kL = 1.0 / float(lightness_weight)
    kC = float(chroma_weight)
    if mode == "none":
        idx = pal_mod.nearest_index(src, palette, kL, kC)
    elif mode == "floyd":
        idx = _floyd_steinberg(src, palette, float(dither_strength), kL, kC)
    else:
        raise ValueError("unknown dither mode: %r" % dither)

    idx = idx.astype(np.int32)
    if despeckle_threshold and mode != "floyd":
        idx, _ = despeckle(idx, src, palette, threshold=despeckle_threshold,
                           lightness_weight=lightness_weight,
                           chroma_weight=chroma_weight)
    return GridResult(indices=idx, palette=tuple(palette),
                      source_rgb=src, dither=mode)


def _floyd_steinberg(src, palette, strength, kL=1.0, kC=1.0):
    lut = pal_mod._nearest_lut(pal_mod.palette_key(palette), kL, kC)
    pal_rgb = np.array([c.rgb for c in palette], dtype=np.float64)
    work = src.astype(np.float64)
    h, w, _ = work.shape
    out = np.zeros((h, w), dtype=np.int32)
    shift = 8 - pal_mod._LUT_BITS

    for y in range(h):
        for x in range(w):
            old = work[y, x]
            c = np.clip(old, 0, 255).astype(np.int32) >> shift
            k = int(lut[c[0], c[1], c[2]])
            out[y, x] = k
            err = (old - pal_rgb[k]) * strength
            if x + 1 < w:
                work[y, x + 1] += err * (7.0 / 16.0)
            if y + 1 < h:
                if x > 0:
                    work[y + 1, x - 1] += err * (3.0 / 16.0)
                work[y + 1, x] += err * (5.0 / 16.0)
                if x + 1 < w:
                    work[y + 1, x + 1] += err * (1.0 / 16.0)
    return out


def despeckle(indices, source_rgb, palette, threshold=6.0, passes=1,
              lightness_weight=1.5, chroma_weight=1.0):
    """Remove lone studs that no neighbour shares.

    Downscaling a picture leaves anti-aliased pixels along every edge, and
    those land on odd palette colours -- a single green stud between blue and
    white.  A stud is only swapped for a neighbouring colour when doing so
    costs almost nothing (``threshold`` in CIEDE2000 units), so genuine
    one-stud detail, like a bird against the sky, survives.
    """
    kL, kC = 1.0 / float(lightness_weight), float(chroma_weight)
    pal_lab = pal_mod.srgb_to_lab(np.array([c.rgb for c in palette], float))
    src_lab = pal_mod.srgb_to_lab(np.asarray(source_rgb, float))
    cost = pal_mod.delta_e_2000(src_lab[:, :, None, :], pal_lab[None, None, :, :],
                                kL=kL, kC=kC)                      # (H, W, P)
    idx = np.asarray(indices).copy()
    h, w = idx.shape
    changed_total = 0
    for _ in range(max(1, int(passes))):
        out = idx.copy()
        changed = 0
        for y in range(h):
            for x in range(w):
                own = idx[y, x]
                neigh = idx[max(0, y - 1):y + 2, max(0, x - 1):x + 2].ravel()
                neigh = neigh[neigh != own]
                if neigh.size == 0 or (idx[max(0, y - 1):y + 2,
                                           max(0, x - 1):x + 2] == own).sum() > 1:
                    continue
                options = np.unique(neigh)
                best = options[np.argmin(cost[y, x, options])]
                if cost[y, x, best] - cost[y, x, own] <= threshold:
                    out[y, x] = best
                    changed += 1
        idx = out
        changed_total += changed
        if not changed:
            break
    return idx, changed_total


def grid_rgb(result: GridResult) -> np.ndarray:
    """(H, W, 3) uint8 image of the quantised grid."""
    pal_rgb = np.array([c.rgb for c in result.palette], dtype=np.uint8)
    return pal_rgb[result.indices]


def _box_blur(img, radius=1):
    pad = np.pad(img.astype(np.float64), ((radius, radius), (radius, radius), (0, 0)),
                 mode="edge")
    acc = np.zeros_like(img, dtype=np.float64)
    n = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            acc += pad[radius + dy:radius + dy + img.shape[0],
                       radius + dx:radius + dx + img.shape[1]]
            n += 1
    return acc / n


def fidelity(result: GridResult) -> dict:
    """How close the brick version is to the original, in CIEDE2000 units.

    ``mean_delta_e`` compares stud to pixel.  ``mean_delta_e_at_distance``
    compares 3x3 stud averages, which is what your eye actually integrates
    when you step back from the finished mosaic -- it is the fairer score for
    a dithered build.
    """
    out_rgb = grid_rgb(result)
    src_lab = pal_mod.srgb_to_lab(result.source_rgb.astype(np.float64))
    out_lab = pal_mod.srgb_to_lab(out_rgb.astype(np.float64))
    d = pal_mod.delta_e_2000(src_lab, out_lab)

    src_b = pal_mod.srgb_to_lab(_box_blur(result.source_rgb))
    out_b = pal_mod.srgb_to_lab(_box_blur(out_rgb))
    db = pal_mod.delta_e_2000(src_b, out_b)

    return {"mean_delta_e": float(d.mean()),
            "median_delta_e": float(np.median(d)),
            "p95_delta_e": float(np.percentile(d, 95)),
            "max_delta_e": float(d.max()),
            "mean_delta_e_at_distance": float(db.mean()),
            "p95_delta_e_at_distance": float(np.percentile(db, 95))}
