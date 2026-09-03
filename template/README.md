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
- **98 of 192 tone images pass all six checks.**
- **94 generations remain**, listed in the queue below.

### Key method: chained sibling edits (learned from 6 failed re-dos)
Editing a tone variant straight from `base/` repeatedly overshot or undershot on garments whose base
skin sits far from the target tone (M13/deep overshot twice in opposite directions; M15's whole set
came out compressed and too dark). Generating each variant from its **nearest already-correct sibling**
with a *small* instruction ("slightly darker", "only a touch lighter") converged first time:
M13/deep from M13/ebony -> 72.9 PASS; M10/ebony from M10/deep -> 58.8 PASS.
For M15 the next pass will build the ladder as a chain: fair from base, light-warm from fair,
light-tan from light-warm, ebony from deep - which enforces spacing by construction.

### QC method notes (what does NOT work — learned the hard way)
Three automated defect proxies were tried and rejected after validation, because e### Queue (priority order)
1. `light-tan/M11-pathani` (120.7, collides with its medium-brown 120.3) and `ebony/M11-pathani`
   (stale, pre-base-fix) - M11's other 4 tones pass.
2. `M15-let-ai-decide` - `fair` (158.5), `light-warm` (139.4), `light-tan` (109.9) off-anchor and
   `ebony` (78.9) colliding with `deep` (75.6). Redo via the chained-sibling method above;
   `medium-brown` and `deep` already pass. All 6 are now derived from the current base, so the old
   stale-lineage concern for M15 is closed.
3. `W1-saree` all 6 tones - visually confirmed defect: tones carry scalloped/torn blotches on the
   lower drape that the current base does not have.
4. `W2-lehenga-choli` all 6 tones (stale by provenance; `deep`/`ebony` also measure +7%/+17% edge
   energy) then `W5` (4) and `W6`-`W17` (72, never generated; includes overwriting the 3 `light-tan`
   pixel-copy placeholders for W11/W14/W16).

tone sibling instead of the base).
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
