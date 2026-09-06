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
tools/mask_blue.py                       tone harness imported by mask_code (skin region, sweep test)
tools/tone.py                            the six-complexion step, run per master
tools/tone-ladder.json                   the six rungs and the naturalness gate - one definition, used everywhere
tools/tone-exclusions.json               the few boxes per outfit that must never tone (footwear, lit sweep)
tools/make_tones.py                      generates all 192 frames, verifies each, writes the report
tools/tone_sheets.py                     rebuilds the head/legs close-ups and the two contact sheets
tools/tone_swatch.py                     the 6-chip colour strip (`_qc/skin-tones.png`), measured on the photos
as-shot/ light-warm/ light-tan/ medium-brown/ deep/ ebony/   32 frames each, 192 total
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
python3 template/tools/make_tones.py               # build all 192 frames, verifying each render exactly (1 level)
python3 template/tools/make_tones.py --verify-only # re-measure the delivered JPEGs (6-level ringing allowance)
python3 template/tools/tone_sheets.py              # rebuild the four review sheets (6 columns; --with-source appends the master)
python3 template/tools/tone_swatch.py               # rebuild the 6-chip swatch strip, re-measured from the files
python3 template/tools/make_tones.py --tones as-shot   # refresh one rung (e.g. after a master is replaced)
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
correct across the five driven rungs (the sixth card is the master itself, so its pixels are the same by definition). Two rules make it hold rather than nearly hold: hue-window rejection
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
## The six complexions
`<tone>/<ID>-<tone>.jpg`, six folders, 192 frames. The complexion is **not** a prompt: each frame is
the master with its skin region re-toned by a measured transform, so the garment, the hair, the
props and the sweep are the same pixels across the cards and only the skin moves.

The shop offers five re-toned cards plus **`as-shot`**, which is the master itself served as its own
complexion: `template/tools/tone-ladder.json` marks it `"as_shot": true`, `make_tones.py` copies the
file instead of editing it, and the check on it is exact rather than a tolerance - all 32 must decode
pixel-for-pixel equal to `base/`. It has its own folder so the site can treat six cards alike.
`fair` (190/24) was dropped on instruction: six tones, and the palest rung read cooler and flatter
than the shop wanted.

`tools/tone-ladder.json` is the single definition of a complexion, in the units `tools/tone.py`
measures — `skinL` is the mean of a pixel's three channels, `skinS` is its highest minus its lowest,
both 0–255, averaged over the frame's skin region:

| rung | `light-warm` | `light-tan` | `medium-brown` | `as-shot` | `deep` | `ebony` |
|---|---|---|---|---|---|---|
| skinL | 178 | 164 | 148 | the master, 115-165 as shot | 130 | 114 |
| skinS | 30 | 35 | 38 | 88-102 as shot | 41 | 44 |

`as-shot` sits in the *middle* of the ladder by lightness, not at an end - it is the model's own
wheat-olive skin, which is deeper and far more saturated than `light-warm`. The step gate (T4,
neighbours at least 8 apart) is therefore measured across the five driven rungs only; the as-shot
card is reported against its nearest driven neighbour instead of being forced.

The masters measure 115–164 at `skinS` 54–99, i.e. over-saturated for studio exposure, so
`light-tan` is a correction rather than a copy of the base. `tone_pixels` moves lightness with a
gamma curve solved by bisection against the measured mean — never a clipped constant shift, which
is what left the palest rungs 6–8 L short — and equalises chroma by scaling each channel's offset
from its own mean.

`tools/make_tones.py` generates and then re-measures every frame, refusing to ship one that fails:
**T1** 0 px of any piece mask's own cloth changed (this is why a single mask set serves all six
complexions); **T2** nothing changes that is not skin — tested on the sweep's own colour family
(cool grey / flat chroma) rather than by the skin detector, because a guard that defines "outside
the skin" with the mask under test passes exactly when the mask is wrong; **T3** the frame lands
within 4.0 of its rung; **T4** the result stays natural (`skinS` 18–52, neighbouring rungs ≥ 8
apart). `_qc/tones-report.json` carries the per-frame numbers.

Two rules the first passes got wrong, now enforced in `mask_blue.skin_region`: luminance may not be
an *inclusion* test (a lit forearm is brighter than the backdrop, and W12's legs stayed untanned
while her face went fair), and the region must exclude hair that falls past the head box, or a
model's plait tans along with her skin. Skin's *hue* is also checked against the head's own hue
(±45°), because `R > B` is not enough: magenta cloth and a gown's bounce light on the floor are
both "warmer than blue" and were being tanned as skin.

`tools/tone-exclusions.json` is the one curated part of this step: a handful of boxes, per outfit,
that the tone must never touch — pale footwear whose colour genuinely lies inside skin's envelope
(W12's nude pumps went grey as her face went fair, W4's tan chappals) and patches of sweep that a
gown's bounce light makes warm and chromatic under a hem (W1, W6, W11, beside M6's and M13's
sandals). No detector can separate those from a bare leg without cutting the leg too: a geometric
"only a limb that continues from the hem" rule was written, tested and removed, because it left
W12 with one toned leg and one untanned one and stopped neither the pumps nor the smear. The
masters are fixed-pose renders, so for 32 known frames a checked box is the exact instrument, and
**T5** measures that nothing inside one changed. Boxes can only remove pixels from the region.

`python3 template/tools/tone_sheets.py` rebuilds the review sheets (`_qc/tone-head.png`,
`tone-legs.png`, `tones-men.png`, `tones-women.png`). Read them, not just the report: every defect
named above was found by looking at a sheet after its numbers had passed. `_qc/skin-tones.png` is the
swatch strip the shop can quote from, built by `tools/tone_swatch.py`: **six** chips, one per card,
each measured on the delivered photos rather than picked from a palette. No master chip - `as-shot` is
the master, so printing it again reads as a seventh card, and the sheets that mount the tiles keep the
source frame behind `--with-source` for the same reason.

`tools/tone.py` is both the colour maths and a one-frame command. Run on one of these 32 masters with
`--tone`, it defers to `make_tones.tone_one`, because there are two skin finders in this kit and the
older one (`tone.skin_mask`: silhouette + warmth) is for arbitrary photos - on these frames it tones
688k px instead of 20k, backdrop included. Wiring the CLI to the batch's own region closed a 159-level
disagreement between a hand-run render and a shipped frame; the two now differ by 0 in memory and by
JPEG decode only on disk. A rung marked `"as_shot"` is copied, not edited, by both paths.

The shop's picker shows the cards in `picker_order` (a key in `tone-ladder.json`): **as-shot first, then
light to dark** - as-shot, light-warm, light-tan, medium-brown, deep, ebony. It lives in the same file as
the colour targets so the site has one thing to read, and nothing in the pipeline sorts by it: the gates
still use `rank`, which is measured lightness, so merchandising order can never move a complexion target.

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
fine. `tone_sheets.crop_for` now derives each window from that figure's own rows via the same ruler
`reframe_master` uses, so a crop can no longer indict a healthy master.
