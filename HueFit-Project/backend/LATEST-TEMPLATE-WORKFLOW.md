# Latest 32-template and six-complexion workflow

The approved catalogue contains 32 outfits, 74 corrected source masks, 58 semantic runtime masks, and six committed complexion images per outfit.

Approved native complexion keys:

- `light-warm`
- `light-tan`
- `medium-brown`
- `as-shot`
- `deep`
- `ebony`

The six public depth labels map one-to-one in light-to-dark order:

- `fair` -> `light-warm`
- `light` -> `light-tan`
- `wheatish` -> `medium-brown`
- `medium` -> `as-shot`
- `dusky` -> `deep`
- `deep` -> `ebony`

Use only the complexion images committed by the design teammate under `template/` on GitHub `main`. Do not generate replacement complexions in the backend. All six variants share the same reviewed garment masks.

Run the all-in-one PowerShell workflow to download the pinned GitHub source, verify all 192 committed tone files, exercise all 192 backend template/tone combinations locally, synchronize Supabase safely, run six live Supabase-backed renders, and publish the verified backend snapshot.

No deployment is performed by this workflow.
