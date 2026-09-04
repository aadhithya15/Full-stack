"""One shared definition of "background", used by BOTH tools/flatten_backdrop.py (what to paint)
and tools/check_backdrop.py (what to measure) -- they must never disagree, or the gate certifies a
defect or rejects a clean file.

background = pixels that are
  field-grey  (saturation <=10 and |L-128| <=30)
  AND outside a 1px dilation of the body silhouette (largest non-field component, 9px closed)
  AND ( connected to a frame edge, i.e. the real studio field
        OR an enclosed pocket that is small AND centred on 128 )

The enclosed-pocket clause is needed because background also occurs INSIDE the outline: the gap
between an arm and a torso, the space between the legs, the void under an asymmetric hem. Pockets are
accepted only when their MEAN sits within 12 levels of 128, which is what separates them from a
shadowed cloth crease (those measure ~150): painting a crease would burn a flat grey smudge into the
garment, which is the glitch this catalogue is being rebuilt to avoid.
"""
import numpy as np
from scipy import ndimage

MIN_POCKET = 100          # px: size is NOT the discriminator (a 372px sliver of real background in
                          # M11-pathani was refused by a 500px floor and stayed bright); surroundings are
MAX_POCKET_FRAC = 0.08    # of frame: above this it is too big to trust as background
POCKET_L_TOL = 40         # levels: an enclosed patch may sit this far off 128 and still be painted
CLOTH_SURROUND_MAX = 0.75 # what actually separates a pocket from a crease is what wraps it

# A hard +-12 luminance rule was tried and is wrong: M11-pathani carries a 16x207px strip of real
# background in the gap between arm and torso at mean L=144, so +-12 refused it -- which left a bright
# sliver ringed by freshly painted 128, a more visible artifact than not painting at all. A crease
# inside fabric is wrapped almost entirely by bright cloth (measured 97% L>180 in W1-saree); a gap of
# background is wrapped partly by the field itself (53% for that strip). So: paint the enclosed patch
# if it is NOT cloth-wrapped, whatever its mean, up to +-40 of 128.


def body_silhouette(X):
    L = X.mean(2); S = X.max(2) - X.min(2)
    nf = ~((S <= 10) & (np.abs(L - 128) <= 30))
    lab, n = ndimage.label(nf, structure=np.ones((3, 3)))
    if n == 0:
        return np.zeros_like(nf)
    cs = np.bincount(lab.ravel(), minlength=n + 1)
    return ndimage.binary_closing(lab == (int(np.argmax(cs[1:])) + 1), np.ones((9, 9)))


def background(X):
    """(bg, field) boolean masks for one frame."""
    L = X.mean(2); S = X.max(2) - X.min(2)
    field = (S <= 10) & (np.abs(L - 128) <= 30)
    body = body_silhouette(X)
    if not body.any():
        return field & False, field
    protect = ndimage.binary_dilation(body, np.ones((3, 3)), iterations=1)
    cand = field & ~protect
    lab, n = ndimage.label(cand, structure=np.ones((3, 3)))
    if n == 0:
        return cand & False, field
    border = set(np.unique(np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]]))) - {0}
    cs = np.bincount(lab.ravel(), minlength=n + 1)
    ml = np.bincount(lab.ravel(), weights=L.ravel(), minlength=n + 1) / np.maximum(cs, 1)
    solid = ndimage.binary_fill_holes(body)
    ins = np.bincount(lab.ravel(), weights=solid.ravel(), minlength=n + 1) / np.maximum(cs, 1)
    keep = set(border)
    for i in range(1, n + 1):
        if i in border:
            continue                                   # the open studio field, always painted
        if cs[i] < MIN_POCKET or abs(ml[i] - 128) > POCKET_L_TOL:
            continue
        if ins[i] < 0.5:
            keep.add(i)                                # outside the body outline => background, and
            continue                                   # nothing on the garment can live there
        if cs[i] > MAX_POCKET_FRAC * L.size:
            continue                                   # a huge interior region is shading, not a pocket
        sel = lab == i
        band = ndimage.binary_dilation(sel, np.ones((3, 3)), iterations=8) & ~sel
        if band.sum() < 50 or float((L[band] > 180).mean()) <= CLOTH_SURROUND_MAX:
            keep.add(i)                                # interior patch, not cloth-wrapped => a gap
    return cand & np.isin(lab, list(keep)), field
