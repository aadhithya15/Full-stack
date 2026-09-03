# HUE FIT — template/ (skin-tone catalog system)

Clean structure. One base model set + 6 skin-tone variant folders + one universal masking folder.

## Structure
```
template/
  base/                 32 master garment photos (768x1376, photorealistic, #808080 grey backdrop)
                        M1..M15 = men's outfits, W1..W17 = women's outfits (incl. "let-ai-decide" lines)
  fair/                 32 photos — very fair, light skin tone
  light-warm/           32 photos — fair to light warm skin tone
  light-tan/            32 photos — light tan, medium skin tone
  medium-brown/         32 photos — warm medium-brown skin tone
  deep/                 32 photos — deep brown skin tone
  ebony/                32 photos — rich dark, ebony skin tone
  universal-masking/    Garment masks (white = garment, black = everything else).
                        One mask per garment piece; multi-piece outfits carry multiple masks.
```

Every tone folder is pixel-identical to `base/` except skin pixels (face, neck, hands, arms).
Same model, same pose, same garment, same background, same lighting across all 6 tones for any given outfit ID.

## Naming
Photo: `<PhotoID>-<desc>.jpg`  e.g. `W1-saree.jpg`, `M1-shirt-trousers.jpg`
Mask:  `<PhotoID>-<piece>-mask.png`  e.g. `W1-blouse-mask.png`, `W1-saree-mask.png`

## Garment IDs
Men: M1-shirt-trousers, M2-blazer-chinos, M3-two-piece-suit, M4-three-piece-suit, M5-tuxedo,
M6-kurta-pajama, M7-kurta-dhoti, M8-nehru-jacket-kurta, M9-sherwani, M10-bandhgala,
M11-pathani, M12-polo-jeans, M13-casual-coord, M14-formal-shirt-pants, M15-let-ai-decide

Women: W1-saree, W2-lehenga-choli, W3-anarkali, W4-salwar-suit, W5-kurta-palazzo,
W6-sharara, W7-gharara, W8-evening-gown, W9-maxi-dress, W10-midi-dress,
W11-jumpsuit, W12-skirt-blouse, W13-blazer-trousers, W14-western-coord, W15-kaftan,
W16-jeans-top, W17-let-ai-decide

## Usage
Recolour = replace pixels inside a mask (white) with the shop's target colour; outside-mask
pixels stay untouched. Masks are zero-skin/zero-background by construction.

## Status (verified by tools/check_backdrop.py, never by eye)

### The backdrop rule, and the two ways it was previously gotten wrong
Background must be one flat #808080 (L=128) **edge to edge**, no lighter panel behind the model, no
darker outer margins, no enclosed bright sliver. Two bugs kept that from being true:

1. **A paint window narrower than the field.** The first flattener only repainted pixels within +-14 of
   128 and only those *connected to the frame border*. A panel sitting at 137 was therefore left
   standing while the field around it went to exactly 128 -- which SHARPENED the edge it was meant to
   remove. `bgmask.py` now paints every field pixel (+-30) that is border-connected, plus enclosed
   pockets.
2. **A gate narrower than the defect.** The gate used to measure only pixels within +-8 of 128, so
   blocks averaging 137 were invisible to it and files were certified clean while still showing the
   panel. The gate now measures whatever `bgmask.background()` returns, so tool and gate cannot
   disagree, and it includes interior pockets (16x207 px arm-to-torso sliver at 144 in
   `light-warm/M11-pathani`, 1,490 px at 146 in `light-tan/M7-kurta-dhoti`, both real background).

Pockets vs cloth creases are separated by **what surrounds them**, not by luminance: a crease inside
fabric is wrapped ~97% by bright cloth (L>180), a background gap only ~53-64%. Painting a crease
would burn a flat grey smudge into the garment -- the glitch this catalogue is being rebuilt to avoid.

### One pass only
`tools/flatten_backdrop.py` must be run **once** per generation batch. Re-running it on its own output
creeps about 0.3% of silhouette area per pass (edge ringing qualifies as field, gets painted, shaves
the garment); five passes moved area 3.9% and changed subject-core pixels by up to 44 levels. After a
batch: flatten (once) -> `python3 template/tools/check_backdrop.py` -> audit subject integrity against
the previous commit.

### Verification applied to every pushed image
1. dimensions 768x1376 == base; 2. not a byte-identical copy of the base (catches placeholders);
3. edits confined to skin (changed pixels inside subject bbox, garment/background untouched);
4. backdrop uniform: 96px block means over the shared background mask have spread <=2.0,
   |mean-128| <=1.5, and 16px cell-mean std <=0.30 (`tools/check_backdrop.py`, exit 0);
5. no static/glitch artifact; 6. skin tone on an auto-located face patch within +-15 of its anchor and
   neighbours >=8 apart.

### Skin-tone metric -- and why the old one passed files it should not have
Anchors used to be read off a `face_patch` slice (top 18% of the subject bbox, central 60% of the
width). That window includes background and collar pixels, so it reported all six tones of a batch as
157-173 regardless of the actual skin, and it made an over-dark re-tone look on-anchor. Tones are now
measured on the **saturated upper-third skin cluster** only: pixels with saturation >18 and |L-128| >18
within the top 45% of the frame (head and shoulders), which needs >=500 pixels and ignores background,
cloth and the wall.

Catalogue medians on that metric (target per tone, tolerance +-15, neighbours must stay >=8 apart --
cross-garment std is 5-11, so +-15 is about 1.5-2 sigma):
  fair: 179.3
  light-warm: 162.6
  light-tan: 146.9
  medium-brown: 98.1
  deep: 72.9
  ebony: 63.6


### Counts (recounted from disk, not from a log)
- 32 `base/` masters: all clean, all pass the backdrop gate.
- **101 of 192 tone images usable** (126 tone files present, 22 carry pre-fix fabric and 3 fail the skin-tone metric).
- **91 remain** = 66 never generated + 22 present-but-stale-fabric + 3 off-tone (M15/light-tan, M3/light-tan, W3/medium-brown).
- Stale fabric: W1/deep, W1/ebony, W1/light-tan, W10/light-tan, W11/light-tan, W12/light-tan, W13/light-tan, W14/light-tan, W15/light-tan, W16/light-tan, W17/light-tan, W2/deep, W2/ebony, W2/fair, W2/light-tan, W2/light-warm, W2/medium-brown, W5/light-tan, W6/light-tan, W7/light-tan, W8/light-tan, W9/light-tan.
- No two tone files in the catalogue are byte-identical (0 duplicate groups).

### `M15-let-ai-decide` re-cut (outfit, not backdrop)
The old M15 master was a bandhgala-style jacket, the same garment family as M10 (silhouette overlap
0.79 vs 0.96 for a genuine re-tone of one file), so the AI-decided card was a near-duplicate of the
bandhgala card. It is now a belted asymmetric-hem kurta-jacket over tapered trousers -- the only
diagonal hem in the catalogue (measured 86 px hem step, y1291 vs y1205), with the same model, pose,
framing and lighting as the old frame. A linen blazer set was rejected as the replacement because M2,
M3, M4 and M5 already occupy that silhouette. Its six tone files must be regenerated against the new
base (the old ones were retired), and `unified-masking/` must redo M15's masks: the garment outline
changed, so any existing M15 mask no longer matches.
