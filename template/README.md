# HUE FIT — `template/` (rebuild in progress, catalogue of 32 outfits × 6 tones + piece masks)

This folder was wiped by `cb4911e` and is being rebuilt from scratch on a verified pipeline, per request:
the previous images were too soft and the recolour looked faded. This README describes what is on disk
**now**, measured by the scripts in `tools/`, not a wish list.

## Structure

```
template/
  base/                 32 master garment photos (768x1376, #808080 field, #D5D5D5 garments)
                        M1..M15 men, W1..W17 women. The base IS the light-tan frame.
  fair/  light-warm/  light-tan/  medium-brown/  deep/  ebony/
                        32 photos each, pixel-identical to base/ except skin L/S.
  universal-masking/    one PNG per garment PIECE, 768x1376, 255 = that piece, 0 = everything else.
  pieces.json           machine-readable manifest: outfit -> pieces -> mask file, with occlusion flags.
  tools/                the pipeline and its gates (run from repo root).
```

## Current state (recounted from disk)

| | present | gates |
|---|---|---|
| `base/` | **19 / 32** — M1…M15, W1…W5 (W2 excluded: fabric grain) | 19 PASS / 0 FAIL |
| tone folders | **19 each = 114 / 192** | 19 PASS / 0 FAIL, pose-lock **19/19** in all six |
| `universal-masking/` | **25 masks / 10 outfits** auto-resolved; 9 outfits rejected pending model segmentation | see below |
| remaining bases | 22 (M11–M15, W1–W17) | generation-limited: 10 images per turn |

Rejected predecessor batch measured on the same corrected gates: **0 PASS / 32 FAIL** — every old frame
failed skin saturation (S 53–77 against a target band of 18–52), and 11 of 32 failed backdrop uniformity.

## The gates (all numeric, nothing certified by eye)

`tools/audit.py <folder> [--iou] [--base template/base]`

- `spread/off/cstd` — backdrop uniformity measured on **open field only**
- `delta` ≥ 26 — garment luminance above the 128 field. This is the anti-fade gate: the old batch sat at
  39.6–48.1 on the worst frames, which is exactly what reads as washed out. New frames measure 52–74.
- `sharp` ≥ 1.1 — median |Laplacian| inside the garment, the anti-soft gate (old: 1.67, new: 3.0–5.3)
- `sat` 18–52 — skin saturation. **The shop asked for colour that is not strong**, so this band replaced
  the old 6–78. The generator renders Indian skin at 61–83 on flat grey and it reads as a fake tan.
- `--base` pose lock: silhouette IoU ≥ 0.985 and backdrop movement ≤ 0.2% vs the base master. Measured
  result: IoU 0.999+, movement 0.000%. This is what makes ONE mask valid for all six tones.

### The gate bug that was fixed here (important if you reuse these scripts)

The backdrop mask was `(saturation<=10) & |L-128|<=30` outside the body outline — but `body_silhouette()`
leaves holes at the arm/torso gaps, and **light-grey cloth is achromatic and sits within ±30 of 128 in
shade**, so the gate sampled fabric *inside* the silhouette and failed clean frames (M6 measured 3.41
on "background" blocks whose inside-silhouette fraction was 1.00). The definition now excludes a 2px
dilation of the filled silhouette in `audit.py` and `check_backdrop.py`. Before this fix the catalogue
would have been rebuilt chasing a defect that was in the ruler.

## Tone ladder (natural, deliberately not strong)

`tools/tone-ladder.json` — targets are measured on the saturated upper-third skin cluster, same
definition as the gate. Steps of 12–18 L keep the six cards reading as one ramp; the old ladder jumped
48 (146.9 → 98.1) and looked like two groups.

| tone | L | S | note |
|---|---|---|---|
| fair | 190 | 24 | cool-neutral, barely warm |
| light-warm | 178 | 30 | soft beige, no orange |
| light-tan | 164 | 35 | **= the base masters** |
| medium-brown | 148 | 38 | the most common shade in the market |
| deep | 130 | 41 | warm and clear, never muddy |
| ebony | 114 | 44 | rich dark brown, stops short of charcoal |

Tones are produced by `tools/tone.py`, a measured transform of skin L/S on the SAME pixels, not by
regenerating the frame. That is what keeps the six variants pixel-locked so a single mask fits all of
them, and it is why no segmentation model or fine-tune is involved: garment masking is geometry and
luminance against a flat grey field, skin colour never enters it.

## Pipeline

```
python3 template/tools/build_batch.py <raw-folder-of-9:16-frames>
  -> normalize (centre-crop + one LANCZOS pass to 768x1376)
  -> flatten backdrop to exact 128, ONE pass (re-running shaves ~0.3% of silhouette each time)
  -> re-tone base skin onto the light-tan anchor
  -> emit the other five tone files
  -> audit + pose-lock, exit 1 on any failure
```

`tone.py`'s skin detector excludes the hair void below the head and rejects components that start below
72% of frame height — without that, light warm **shoes** read as hands and got tinted (caught on M6).

## Masks — two-stage, and the auto stage is deliberately not trusted alone

`tools/make_masks.py` splits the colour-derived cloth region at detected hem lines. It ships a mask only
when it passes its own validator, and right now that is **10 of 19 outfits**; 9 are reported UNRESOLVED
because a horizontal cut cannot find them:

- M1/M3/M5/M10/M12/M13/M14 report `piece-size-skew` — the seam lands where the shirt ends and the trouser
  begins only sometimes; when the frame is an untucked shirt over trousers the cut falls in the wrong band.
- M4's waistcoat is 21k px behind the jacket lapels, below the 7%-of-cloth floor.
- W5's kurta/palazzo boundary has no width signal at all.

The semantic stage is `tools/seg_decode.py` + `tools/SEGMENT_PROMPT.md`: the image model paints each piece
a flat colour, and the decoder verifies every region against the pixel-level cloth mask (partition,
>=90% coverage, contiguity, area floor, and threshold stability >=0.97 IoU). A region that fails any check
rejects the whole outfit rather than shipping a plausible-looking wrong mask, because a wrong mask puts
shop colour on skin or leaves grey cloth un-recoloured, which is precisely the failure being rebuilt away
from.

`pieces.json` defines 76 masks across 32 outfits, per garment piece, so a two-piece outfit gets a shirt
mask and a trouser mask, and a three-piece suit gets jacket + waistcoat + trousers + shirt = 4. Pieces
flagged `z:0` are present but fully occluded behind an outer layer; the recolour cannot isolate their
pixels from a front view, so recolour them together with the parent piece.

## Known issue for the merchandising pass

Silhouette IoU flags M1 (shirt + trousers) vs M4 (three-piece suit) at 0.936 — technically different
garments, but on a product grid the customer cannot tell the cards apart. Fix by changing fit or length,
not by re-rolling. Nothing exceeds the 0.945 duplicate threshold. M15/W17 in the old set were the same
bandhgala/gown family as M10/W8 and have been re-pinned in `pieces.json`.

## Push notes

Nothing in `backend/`, `backend-inspect/` or `huefit-frontend/` references `template/` yet — the asset
side can be finished independently of wiring the recolour route.
