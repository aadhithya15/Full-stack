# Latest 32-template backend workflow

This workflow is for the repository layout with `template/pieces.json`, 32 base
masters, and 74 universal piece masks. It does not generate AI templates and it
does not deploy the backend.

## What preparation does

- Validates the exact 32-outfit manifest and all 74 binary source masks.
- Rejects source overlap, missing visible pieces, non-binary masks, or a changed
  manifest instead of guessing.
- Removes the reviewed M4 necktie intrusion from the waistcoat mask. The
  correction is fail-closed and must remove 4000-4400 pixels.
- Combines piece masks into 58 semantic colour groups so two AI colours remain
  coherent (for example, blazer plus trousers use colour 1 and shirt uses
  colour 2).
- Keeps the W15 self-fabric belt in the same group as the kaftan.
- Generates six native complexions: fair, light-warm, light-tan,
  medium-brown, deep, and ebony.
- Protects every garment pixel during complexion generation.
- Writes `templates.csv`, `skin-tone-report.json`, and
  `mask-corrections.json`.

## PowerShell 5.1 commands

Run each command on its own line from the backend project folder.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements-template-tools.txt
python .\scripts\prepare_teammate_templates.py C:\path\to\Full-stack --out .\templates\latest-prepared
python .\scripts\upload_templates.py .\templates\latest-prepared --dry-run
python .\scripts\qa_prepared_templates.py .\templates\latest-prepared --out .\templates\latest-qa
```

Expected preparation totals:

```text
prepared 32 templates, 58 masks
generated 192 tone variants
source mask overlap: 0 pixels
reviewed source-mask corrections: 1
M4 waistcoat: removed 4212 necktie pixels
tone garment movement: 0 pixels
```

Expected QA summary:

```json
{
  "templates": 32,
  "prepared_masks": 58,
  "native_tone_outputs": 192,
  "overlap_pixels_max": 0,
  "all_valid_masks_pass_through_exactly": true,
  "recolour_changed_outside_mask_pixels_max": 0
}
```

## Mandatory visual gate

Open and inspect all of these before any upload:

1. `templates/latest-qa/final-all32.jpg`
2. `templates/latest-qa/final-detail-1.jpg`
3. `templates/latest-qa/final-detail-2.jpg`
4. `templates/latest-qa/final-detail-3.jpg`
5. `templates/latest-qa/final-detail-4.jpg`
6. `templates/latest-qa/tone-six-detail.jpg`

Check faces, necks, ears, hands, midriffs, hair, jewellery, shoes, the studio
background, every garment boundary, and every two-colour grouping. Numeric QA
is not a substitute for this review.

Do not upload or deploy until the visual gate is explicitly approved. A later
upload can be run without `--approve` first, leaving rows pending for a final
approval step.
