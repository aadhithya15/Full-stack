# HueFit — masters, piece masks and the tools that prove them

## The one idea that makes masking exact
Every master is photographed **wearing its colour code**: each garment is a flat solid colour and
the colour says which pattern piece it is.

| code | hex | meaning |
|---|---|---|
| rose | `#C2268F` | outermost / upper garment (shirt, kurta, blazer, sherwani, gown) |
| blue | `#1F5FC4` | middle layer (waistcoat, kurta under a jacket, dupatta, inner top) |
| green | `#1E8E3E` | lower garment (trousers, pajama, dhoti, churidar, lehenga, skirt) |

Anything else — white shirt, dark tie, shoes, skin, hair, the backdrop sweep — is deliberately
**uncoded** and owned by no piece. `tools/mask_code.py` classifies pixels in Lab against the codes
and each colour *becomes* one piece mask, so a garment boundary is not detected, it is simply the
colour edge. Nothing is inferred, which is the only reason "exact" is a fair claim here: the earlier
single-colour-per-outfit masters forced the boundary to be guessed, and the guesses were wrong in a
way every coverage metric passed.

## What is in here
```
base/<ID>-<slug>.jpg                     32 masters, 768x1376 sRGB  (M1-M15 menswear, W1-W17 womenswear)
universal-masking/<ID>-<piece>-mask.png  74 masks, 8-bit L, 768x1376, strictly 0 or 255
pieces.json                              manifest: pieces, colour code, z-order, mask path, status
_qc/all32-overlay.png                    every master with every mask painted over it - the review sheet
tools/mask_code.py                       classifier + gates K1-K10, writes the masks
tools/mask_sheet.py                      builds the overlay sheet from the masks on disk
tools/mask_blue.py                       tone harness imported by mask_code (skin band, tone ladder)
tools/tone.py                            the six-complexion step, run per master
```
5 of the 74 masks are intentionally empty (`z:0`): `M3-shirt`, `M4-shirt`, `M5-shirt`, `M9-kurta`,
`M11-patka`. Those garments are either not visible or uncoded (a white shirt, a closed bandhgala's
inner kurta, a waist wrap), so they are recoloured together with their parent rather than shipped
as a fake mask.

## Rebuild and verify
```
python3 template/tools/mask_code.py            # derives every mask from its master, gates each one
python3 template/tools/mask_code.py --proof    # adds tone invariance
python3 template/tools/mask_sheet.py           # regenerates the overlay sheet
```
Gates. An outfit that fails any of them is rejected and ships no masks — that is a hard stop, not a
warning: **K1** one label per pixel, so overlap and gap are identities; **K3** every code owns a
region ≥2% of the outfit's cloth (if the model forgot the waistcoat, that is said out loud); **K4**
lower garment reaches below upper, and no upper/middle garment sits wholly below it; **K5** zero
pixels inside the head ellipse; **K6** off-palette cloth under 6%; **K7** the tone step moves 0 px
of owned cloth; **K8** any code colour present at >5% of cloth must belong to a declared piece;
**K9** skin and hair are carved out of every mask, so a mask cannot contain a face, a hand or a
woman's hair falling across a gown; **K10** the palette must be decidable — measured by relighting
the frame ±6% and requiring no garment to change owner.

## Why one mask set is valid for all six complexions
Tones are made from a master by editing the skin region only; garment pixels are bit-identical.
Gate K7 measures exactly that on the shipped files, so the masks derived once from the master stay
correct across fair → ebony. Two rules make it hold rather than nearly hold: hue-window rejection
(dark complexions drift in Lab toward a code colour, and skin's hue never does), and hard-stopping
the feather of the tone blend at the garment edge.

## Known, on purpose
* Figure scale varies a little between outfits (e.g. `M14`, `W13` are framed smaller than `M12`).
  Masks follow the frame, so nothing breaks; the catalogue grid just needs the same card crop.
* Thin fold shading is left unclaimed rather than grabbed by an aggressive threshold: 2.3k–9.4k px
  per outfit, all inside the garment. A recolour keeps those lines as shading, which is what real
  cloth looks like. `mask_code._assemble` does fill small enclosed holes (≤34 px, ≤0.4% of cloth) so
  a hairline crease does not stay unpainted, and only that — bigger enclosed gaps are backdrop
  between an arm and a torso, and painting those would show.
* Skin tones exist to be generated per outfit into `fair/ light-warm/ light-tan/ medium-brown/
  deep/ ebony/` (6 × 32 = 192 frames); the masks above are shared by all six.
