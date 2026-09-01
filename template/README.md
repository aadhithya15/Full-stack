# HueFit outfit templates (prepared)

30 template + mask pairs, cleaned and validated, uploaded to Supabase
(bucket: templates, table: outfit_templates).

Naming: <dress_type>_<m|f>_01.jpg + <dress_type>_<m|f>_01_mask.png
Masks: pure black/white, exact same pixel size as the image,
WHITE = the primary garment that gets recoloured.

templates.csv = upload metadata (used by scripts/upload_templates.py).

The original raw drop (bigger masks, per-garment files) is in git history
before this commit.

Known issues (design team to redo):
- M12 top mask: sleeves not fully covered (casual-coord rejected)
- W5 kameez/gharara masks: swapped, colour lands on dupatta (gharara rejected)
- W3 palazzo mask: empty file
- W0 blouse mask: covers almost none of the blouse
