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

## Framing: every figure must be whole inside its frame

Reported on one model ("in m4 model there is over crop image problem"), then audited across all 32.
The house numbers, measured off the 32 masters: **figure height median 1237 rows, headroom 77, footroom
58** (a 768x1376 frame, rows counted from the classifier's own view of the figure, not from brightness).
`tools/reframe_master.py --check` prints the table and flags anything cut or cramped; a clean run says
`flagged: none`. `_qc/reframe-before-after.png` shows the three frames before and after with the crown
and feet of each at actual scale, because that is where a cut is visible and a number is not.

Three masters failed it. **M4** had both ends amputated — 67 px of hair already at row 0 and his soles
sliced flat at row 1375, so there was *no slack to shift into*: his figure spanned the entire frame.
**M9**'s shoes ran off the bottom. **W10** was whole but sat 19 px from the top and 3 px from the bottom.

Two routes, and which one applies is decided by the ruler, not by taste:

* **whole but cramped** (W10) — pure geometry. `--pad` scales the figure to the house numbers, aligns
  *the figure* to the house headroom (aligning the frame instead pushes the feet out of the bottom, which
  manufactures the defect it is fixing) and fills what is left with the master's own edge row, so no
  pixel is invented and no model call is needed.
* **cut by the edge** (M4, M9) — the missing caps have to come from somewhere, and only a generative
  pass is allowed to supply them. `--pad` builds the correctly-framed frame with flat backdrop in the two
  bands; the image model is handed *that* and asked for nothing but the hairline and the sole edges;
  `--restore` pastes the approved master back everywhere except those two bands, feathered and overlapping
  the cut by 16 rows so no seam survives. Then `--install`, which refuses the candidate unless the
  framing is clean and every garment's coded area moved by the *same* factor (a render that quietly
  recoloured or reposed him moves one code and not the others — that is a different photograph), and
  unless the masks re-derive with zero overlap and zero head-room violations.

Dead ends, recorded because they are tempting: **mirroring the pixels beside a cut into the blank band**
produces a second pair of eyebrows above his hairline, and asking the model to "zoom out" without the
padded frame gets you the same tight crop re-rendered (the size gate caught it: 848x1264 for a 768x1376
request, rejected rather than squashed, because a resized frame moves every garment off its mask).

After any install: `mask_code.py <the master>`, `make_tones.py --outfits <ID>`,
`make_tones.py --verify-only`, `mask_sheet.py`, `tone_sheets.py`, then the batch previews. The previous
master is kept at `_qc/<ID>-before-reframe.jpg`.

The review sheets had a framing bug of their own, and it is worth separating from the above: `CROPS`
used absolute windows written against M1, so on M4 the *sheet* chopped his face off — the picture was
fine. `crop_for` (in the complexion-card sheets, delivered with the tone batch) now derives each window from
that figure's own rows via the same ruler `reframe_master` uses, so a crop can no longer indict a healthy
master.
