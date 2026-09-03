# HUE FIT — `template/` (32 outfits × 6 tones + piece masks)

Rebuilt from scratch on a numeric pipeline after the previous catalogue was deleted: its frames were soft
and washed out and its recolour looked faded. Everything below is measured by `tools/audit.py`, not judged
by eye.

## Structure

```
template/
  base/                 master garment photos, 768x1376, #808080 field, #D5D5D5 garments
                        M1..M15 men, W1..W17 women. The base IS the light-tan frame.
  fair/ light-warm/ light-tan/ medium-brown/ deep/ ebony/
                        32 photos each, pixel-identical to base/ except skin L/S.
  universal-masking/    one PNG per garment PIECE, 768x1376, 255 = that piece, 0 = everything else.
  pieces.json           manifest: outfit -> pieces -> mask file, with z (occlusion) and status.
  tools/                pipeline + gates.
```

## State (recounted from disk)

| | on disk | gates |
|---|---|---|
| `base/` | **29 / 32** | 29 PASS / 0 FAIL |
| tone folders | **29 each = 174 / 192** | 29 PASS / 0 FAIL, pose-lock **29/29** in all six |
| `universal-masking/` | **14 masks / 6 outfits** (M6, M7, M9, M11, M15, W3) | validated, see below |

**Missing 3 bases → 18 tones:** W7-gharara (garment delta 41.1, faded), W15-kaftan (delta 40.9 + spread
2.23), W16-jeans-top (backdrop spread 2.20). These were carried over from the pre-rebuild batch and are
the only survivors that still fail; they must be regenerated, not patched — brightening faded cloth toward
210 clips the fabric, and a second flatten pass shaves the silhouette.

10 of 13 carried-over women's outfits were **salvaged rather than regenerated**: they failed only the new
skin-saturation band, which is a colour transform (`tools/tone.py`), not a re-roll. That saved 130 image
generations, which at 10 per turn is 13 turns.

## Gates

`python3 template/tools/audit.py template/base --iou` and
`python3 template/tools/audit.py template/<tone> --base template/base`

| check | limit | why |
|---|---|---|
| backdrop spread / offset / cell-std | ≤2.0 / ≤1.5 / ≤0.30 on 96px blocks | one flat #808080 field, edge to edge |
| `delta` (garment L above 128) | **≥45** | the anti-fade gate. Raised from 26 after W15 measured 39.6 and passed — that IS the washed-out look |
| `sharp` (median \|Laplacian\| in cloth) | ≥1.1 | the anti-soft gate. W2 was rejected at sharp 21.0: fabric grain, not detail |
| `sat` (skin cluster) | **18–52** | "not strong": the generator renders Indian skin at 61–83 = sprayed tan |
| `sil` (body area) | 12–46% of frame | catches crops and zoomed-out framing |
| pose lock | silhouette IoU ≥0.985 vs base, backdrop moved ≤0.2% | **this is what makes one mask serve all six tones** |

Two bugs found and fixed in the gate itself, both of which would have caused wrong work:
1. the backdrop mask sampled **light-grey cloth inside the silhouette** (achromatic, within ±30 of 128),
   failing clean frames — it now excludes a 2px dilation of the filled silhouette;
2. `audit.py` had no fade floor, letting 39.6-delta frames through.

## Tone ladder (natural, deliberately not strong)

`tools/tone-ladder.json`. Measured on the saturated upper-third skin cluster, same definition as the gate.

| tone | L | S |
|---|---|---|
| fair | 190 | 24 |
| light-warm | 178 | 30 |
| light-tan | 164 | 35 ← base masters |
| medium-brown | 148 | 38 |
| deep | 130 | 41 |
| ebony | 114 | 44 |

Even 12–18 L steps. The previous catalogue jumped 48 (146.9 → 98.1), which is why the six cards read as
two groups. Tones are colour transforms of one frame, so the pose is byte-locked and no re-roll drift
enters.

## Masks — 32 outfits, piece-level, universal

`pieces.json` defines **76 masks**: one per garment piece (M1 shirt + trousers = 2; M4 three-piece =
jacket + waistcoat + trousers + shirt = 4). Pieces with `z:0` are fully occluded in a front view — the
file exists so the set is complete, but recolour them with their parent piece, not independently.

Two stages, because a purely geometric splitter was caught shipping wrong masks:

1. `tools/make_masks.py` — cloth = inside-silhouette AND achromatic AND bright, head void removed so hair
   is not swallowed into a shirt mask, seams from cloth **width-drop**, piece names paired to bands by
   geometry. Ships only if coverage ≥0.86, no size skew on 2-piece cuts, and every piece's **start row**
   matches its role (an "upper" piece cannot start below 42% of the cloth span). Currently auto-resolves
   **6 of 29 outfits**; the other 23 are reported UNRESOLVED with a reason.
2. `tools/seg_decode.py` + `tools/SEGMENT_PROMPT.md` — grey-on-grey boundaries (blazer vs shirt, saree
   drape vs blouse) are a semantic judgement, so a vision model paints flat colours and the decoder
   verifies each region against the pixel cloth mask: partition, ≥90% coverage, contiguity ≥0.92, area
   floor, and **threshold stability ≥0.97 IoU** (a boundary that moves when you nudge the threshold will
   shimmer across the six tones). Failed verification rejects the outfit; nothing is written.

Rejected-then-shipped would put shop colour on skin or leave cloth grey. That is the exact failure this
rebuild exists to remove, so 14 correct masks are worth more than 76 plausible ones.

## Pipeline for a new batch

```
python3 template/tools/build_batch.py <folder-of-9:16-frames>
  normalize (centre-crop + ONE LANCZOS pass to 768x1376)
  -> flatten backdrop to exact 128, ONE pass
  -> re-tone base skin onto the light-tan anchor
  -> emit the other five tone files
  -> audit + pose-lock; exit 1 on any failure
```

`tone.py`'s skin detector excludes the hair void and rejects components starting below 72% of frame height
— without that, light warm **shoes** read as hands and got tinted (caught on M6).

## Not code-coupled yet

Nothing in `backend/`, `backend-inspect/` or `huefit-frontend/` references `template/` (grep: 0 hits), so
the asset side can be finished independently of the recolour route.
