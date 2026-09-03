# Segmentation prompt for piece masks (used with `tools/seg_decode.py`)

For each outfit, ask the image model to **edit `template/base/<ID>.jpg`** with this prompt, and save the
result as `template/_qc/seg/<ID>-seg.png`. The piece list comes from `template/pieces.json` (visible
pieces only, in top-to-bottom geometric order).

> Repaint this exact photograph, same framing, same pose, same position, same scale, nothing moved.
> Turn it into a flat colour-coded garment segmentation:
> background entirely #808080; skin, hair, face, hands and footwear entirely #101010;
> the <PIECE 1> filled entirely pure red #FF0000;
> the <PIECE 2> filled entirely pure green #00FF00;
> the <PIECE 3> filled entirely pure blue #0000FF;
> the <PIECE 4> filled entirely pure yellow #FFFF00.
> Each colour region must be completely solid, no shading, no gradient, no texture, no outline, no
> anti-aliased fringe, no blending between colours. Regions must not overlap and must not leave grey gaps
> inside the garment. Each piece includes only the part of it that is visible in this front view.
> No text, no labels, no arrows.

Rules that matter:

1. **Piece order = top to bottom by geometry**, the same order `make_masks.py` uses after its band
   sort. M2 is blazer, shirt, chinos (not blazer, chinos, shirt) because the shirt panel shows between
   the lapels above the trouser line.
2. Only `z:1` pieces get a colour. `z:0` pieces are fully occluded in a front view; `seg_decode.py`
   writes an empty mask for them so the file set stays complete without shipping a guessed silhouette.
3. If the model returns soft edges, do **not** blur-fix them. `seg_decode.py` rejects anything whose
   threshold stability is below 0.97 IoU — re-ask instead. A boundary that shimmers at threshold 140 vs
   110 will shimmer across the six tone files too.
4. Never feed it a tone file. Always `base/`, so every mask is anchored to the single geometry the six
   variants share.

Batch: one segment edit per outfit = 32 edits total, run alongside a normal 10-image generation batch.
`seg_decode.py` is the gatekeeper — an outfit that fails verification keeps whatever `make_masks.py`
produced and is reported, not silently overwritten.
