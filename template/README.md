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

## Status (verified by git-history + checksum + per-tone luminance audit, not by hand)

All 32 `base/` masters are regenerated clean (the systemic fabric static/glitch artifact baked into
the original batch is gone; it had propagated into every tone copy made from a base).

### Verification applied to every pushed image
1. dimensions 768x1376 == base; 2. no pixel-copy of base (catches placeholders); 3. edits confined
to skin (changed pixels 2-4%, inside subject bbox, garment/background untouched); 4. backdrop
neutral #808080 (corner deviation <=6, no cast/gradient); 5. no static/glitch artifact; 6. skin tone
measured on an auto-located face patch must sit within +-15 of its tone anchor and neighbours must
stay >=8 apart.

Tone anchors (target face-patch luminance): fair 174, light-warm 158, light-tan 140,
medium-brown 111, deep 80, ebony 67.

### Counts
- **94 of 192 tone images pass all six checks.**
- **98 generations remain** (see queue below).

### QC method notes (what does NOT work — learned the hard way)
Three automated defect proxies were tried and rejected after validation, because each produced
false positives or missed known cases: edge-hard-jump counts inside the garment region (rises with
skin/garment contrast, so it flags correct dark-tone files); cloth-region high-frequency percentile
(identical bands for fresh and stale files); and base-lineage MAD against the pre-fix vs post-fix
base blob (a diffusion re-render aligns with neither). **The gate is: visual inspection of the image
plus a contact-sheet of all 6 tones, combined with provenance** (a tone file committed before its
base was regenerated is treated as stale regardless of how clean it looks).

Tone numbers are still measured automatically (face-patch luminance vs the anchors below) - that
part works and has caught several real defects.

### Queue (priority order)
1. Tone re-dos - `ebony/M10-bandhgala` (76.0, collides with its `deep` 78.5), `light-tan/M11-pathani`
   (148.6, only 5.1 from `light-warm`), `deep/M13-casual-coord` (59.5; two regens overshot in
   opposite directions - try editing the closest on-tone sibling instead of the base).
2. `W1-saree` all 6 tones - visually confirmed: tones carry scalloped/torn blotches on the lower
   drape that the current base does not have; the set no longer matches its own base.
3. `W2-lehenga-choli` 6 tones + `M11-pathani/ebony` - stale by provenance (pre-base-fix).
4. W5 (4) then W6-W17 (72) - never generated; also overwrites the 3 `light-tan` pixel-copy
   placeholders (W11/W14/W16) which measure as OLD-lineage.
5. Deferred pending owner decision: `M15-let-ai-decide` 6 tones are stale by provenance but visually
   clean on triage (12 if `M11`'s other files are counted too) - regenerate only if strict
   base-consistency across every file is required rather than appearance-based.

### Tone anchors (target face-patch luminance; +-15 tolerance, neighbours >=8 apart)
fair 174, light-warm 158, light-tan 140, medium-brown 111, deep 80, ebony 67.

### Remaining stale / never-generated (106)
M10, M11, M15, W1, W2 (6 tones each = 36), W5 (4), W6-W17 (12 sets x 6 = 72, incl. overwriting
`light-tan/W11-jumpsuit.jpg`, `light-tan/W14-western-coord.jpg`, `light-tan/W16-jeans-top.jpg`
which are byte-identical copies of base/).

- `universal-masking/` - carried over from the previous mask build; to be regenerated once the
  base/tone set is complete (masking phase not started).
