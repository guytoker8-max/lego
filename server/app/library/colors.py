"""Colours a brick can be moulded in, and matching a photo's colours to them.

The palette and the CIEDE2000 matching come from the ``legoize`` package
already in this project (vendored under ``app/vendor``): every colour listed
there exists as a real element you can buy, and matching in Lab rather than
RGB is what stops a photo's skin tone landing on lime.

A colour is not automatically available in every part.  ``ColorLibrary``
holds the restriction, so the generator can be told "1x1 bricks only come in
these colours" and will never ask a supplier for something unmouldable.
"""

from __future__ import annotations

import numpy as np

from ..vendor.legoize import palette as _lego

LegoColor = _lego.LegoColor

# Colours that exist across the whole common brick range.  Rare colours are
# real but turn up mainly in plates, so they are opt-in.
COMMON = _lego.get_palette("common")
EXTENDED = _lego.get_palette("extended")


class ColorLibrary:
    """Which colours the generator may use, and how to match into them."""

    def __init__(self, tier: str = "common", exclude_ids: tuple = ()):
        base = COMMON if tier == "common" else EXTENDED
        self.colors = tuple(c for c in base if c.id not in exclude_ids)
        self._by_id = {c.id: c for c in self.colors}

    def get(self, color_id: int) -> LegoColor:
        try:
            return self._by_id[color_id]
        except KeyError:
            raise UnknownColorError(color_id) from None

    def exists(self, color_id: int) -> bool:
        return color_id in self._by_id

    def match(self, rgb: np.ndarray) -> np.ndarray:
        """Nearest real brick colour for each RGB, as indices into .colors.

        ``rgb`` is any array shaped (..., 3) of 0-255 values.
        """
        return _lego.nearest_index(np.asarray(rgb, dtype=np.uint8), self.colors)

    def ids_for(self, indices: np.ndarray) -> np.ndarray:
        lut = np.array([c.id for c in self.colors], dtype=np.int32)
        return lut[indices]

    def rgb_for(self, indices: np.ndarray) -> np.ndarray:
        lut = np.array([c.rgb for c in self.colors], dtype=np.uint8)
        return lut[indices]

    def reduce_to(self, rgb_samples: np.ndarray, n: int) -> "ColorLibrary":
        """The n colours from this palette that best cover these pixels.

        A real set is moulded in a dozen colours, not forty, and that is not
        only a cost decision: restricting the palette makes each colour
        region larger, and larger regions tile into larger bricks. Choosing
        per cell from the full palette gives speckle, and speckle is bought
        as 1x1s.

        Greedy furthest-point cover: take the colour that most pixels want,
        then repeatedly add whichever colour most reduces the error still
        left. Cheap, and it never drops a colour that carries real area.
        """
        samples = np.asarray(rgb_samples, dtype=np.uint8).reshape(-1, 3)
        if len(samples) == 0 or n >= len(self.colors):
            return self
        if len(samples) > 12000:
            rng = np.random.default_rng(3)
            samples = samples[rng.choice(len(samples), 12000, replace=False)]

        sample_lab = _lego.srgb_to_lab(samples)
        pal_lab = np.stack([_lego.srgb_to_lab(np.array(c.rgb, dtype=np.uint8))
                            for c in self.colors])
        # cost[i, j] = perceptual distance from pixel i to palette colour j
        cost = np.stack([
            _lego.delta_e_2000(sample_lab, np.broadcast_to(pal_lab[j], sample_lab.shape))
            for j in range(len(self.colors))
        ], axis=1)

        chosen = [int(cost.argmin(axis=1).astype(np.int64).__array__().min()
                      if False else np.bincount(cost.argmin(axis=1),
                                                minlength=len(self.colors)).argmax())]
        best = cost[:, chosen[0]].copy()
        while len(chosen) < n:
            gain = np.maximum(best[:, None] - cost, 0.0).sum(axis=0)
            gain[chosen] = -1.0
            pick = int(gain.argmax())
            if gain[pick] <= 0:
                break
            chosen.append(pick)
            best = np.minimum(best, cost[:, pick])

        reduced = ColorLibrary.__new__(ColorLibrary)
        reduced.colors = tuple(self.colors[i] for i in sorted(chosen))
        reduced._by_id = {c.id: c for c in reduced.colors}
        return reduced

    def as_dicts(self) -> list:
        return [{"id": c.id, "name": c.name, "hex": c.hex} for c in self.colors]


class UnknownColorError(KeyError):
    def __init__(self, color_id: int):
        super().__init__(color_id)
        self.color_id = color_id

    def __str__(self) -> str:
        return "no such colour in the brick library: %r" % self.color_id


DEFAULT_COLORS = ColorLibrary("common")


def color_by_id(color_id: int) -> LegoColor:
    return _lego.BY_ID[color_id]
