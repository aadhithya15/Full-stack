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

## Status
- `base/` — all 32 masters complete.
- Tone folders — regenerated per-garment across all 6 tones as a rolling batch job (some garments
  still pending full 6-tone coverage; `light-tan` currently mirrors `base/` for garments not yet
  tone-edited).
- `universal-masking/` — carried over from the previous mask build; will be regenerated/replaced
  once the new base/tone set is fully complete.
