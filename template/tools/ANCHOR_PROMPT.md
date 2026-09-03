# Anchor matte prompt (single garment, white on black)

Used by `tools/make_anchor_masks.py`. Send this as an *edit* of the outfit's
`base/<ID>-*.jpg` and save the result to `template/_qc/anchor/<ID>-anchor.png`.
One garment per request - never ask for more than one region at a time.

> Convert this exact photograph into a pure black and white matte. Keep
> framing, pose, position and scale completely unchanged, nothing moved. The
> only thing that stays white is **THE <GARMENT>**: <anatomy of that one
> garment, from where to where>. Paint it entirely solid pure white #FFFFFF
> with a clean crisp edge. Paint every other pixel entirely solid pure black
> #000000, including <each of the other garments, by name>, skin, hair, face,
> hands and shoes. The <garment> must read as one single unbroken white
> silhouette. Pure flat white, pure flat black - no grey, no gradient, no
> shadow, no feathering, no texture, no outline, no text, no labels.

Rules learned the hard way:

- Name the piece the decoder will anchor (`pieces.json` `z: 1`, topmost) -
  `--report` prints which one each outfit needs.
- Say what must be *black*, garment by garment. "Everything else black" alone
  gets ignored and the model mats the whole figure.
- Give the vertical extent ("from the shoulders down to the hem at the calf"),
  not just the name; the model anchors on geometry far better than on vocabulary.
- The decoder rejects a matte under 10% or over 97% of the cloth area, a matte
  that is not ≥90% one connected blob, and a top-of-matte starting below 42% of
  the figure (a shirt cannot begin at the waist). A rejected frame costs nothing
  but a re-roll; a silently wrong mask costs the shop's recolouring.
- Do not re-encode these mattes or resize them by hand: the decoder resamples to
  768x1376 with NEAREST itself, and `cleanup.py` keeps `_qc/anchor/` on purpose
  so a decode can be re-run without paying for the image again.
