# HueFit — masters, tone ladder and universal piece masks

## The one idea that made masking exact
Each master is photographed **wearing its colour code**: every garment is a flat solid colour,
and which colour it is tells the pipeline which pattern piece it is.

| code | hex | meaning |
|---|---|---|
| rose | `#C2268F` | outermost / upper garment (shirt, kurta, blazer, sherwani) |
| blue | `#1F5FC4` | middle layer (waistcoat, kurta under a jacket, inner tunic) |
| green | `#1E8E3E` | lower garment (trousers, pajama, dhoti, churidar) |

White shirt, dark tie, shoes and the backdrop are deliberately **uncoded** and are owned by no
piece. `tools/mask_code.py` classifies every pixel in Lab space against those three colours, plus
a hue-window veto, and each colour *becomes* one piece mask. A garment boundary is therefore the
colour edge, so there is nothing to infer: no seam detection, no segmentation model, no geometry
guessing. That is why the masks can be asserted exact rather than "probably right".

## Files
* `base/<ID>-<slug>.jpg` — masters, 768x1376, sRGB, one per outfit.
* `universal-masking/<ID>-<piece>-mask.png` — 8-bit grey, 768x1376, strictly 0 or 255, one set
  per outfit valid for all six complexions.
* `pieces.json` — the manifest (32 outfits / 74 pieces) and the status of each.
* `_qc/masks-proof.png` — every master with its mask boundaries drawn, next to each piece mask.
* `_qc/code-proof.png` — the same masters at working resolution.

## Rebuild
```
python3 template/tools/mask_code.py            # writes + gates every mask
python3 template/tools/mask_code.py --proof     # adds the tone-invariance gate
```
Gates, all of which must report zero: K1 union == coded cloth; K3 no two pieces share a pixel;
K4 layer order (middle never below lower); K5 no mask pixel inside the head box; K6 off-palette
cloth under 6%; K7 the tone step moves 0 px of owned cloth; K8 any code colour present at >5% of
coded cloth must be owned by a declared piece (this caught a kurta the manifest had forgotten);
K9 no piece pixel is skin, and every code colour stays far from this frame's skin hue.

## Why one set of masks covers six skin tones
Tones are produced from a master by `tone.py`, which edits only the skin region and never touches
garment pixels. Gate K7 measures that claim on the shipped files: re-toning to the palest and the
deepest complexion moves **0 px** inside any piece mask, so the base master's masks stay exact on
all six. (The gate is deliberately stated as "no owned pixel may move" — an earlier version
re-ran the classifier on re-toned frames, which instead measured a feather artefact of my own test
helper and reported phantom disagreements.)

## Status
M1-M10 masked and gated. M11-M15 and W1-W17 need colour-coded masters in the same scheme, then
the 6-tone folders, then masks derive themselves.

## Known limit
Uncoded items are not recolourable, by design: where a shirt is white it ships as an empty mask
with `z:0` (`M3-shirt`, `M4-shirt`, `M5-shirt`) and is recoloured together with its parent; M2's
blue-coded shirt has a real mask. If white shirts must be recolourable, regenerate those masters
with the shirt coded and re-run `mask_code.py`.
