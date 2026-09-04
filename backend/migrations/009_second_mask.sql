-- 009: extra garment masks per template (full-outfit recolouring).
-- Primary garment = mask_url (007). Templates whose outfit has more pieces
-- (kurta+pajama, blazer+trousers, three-piece suit) carry up to two more
-- masks; each masked garment gets its own recommended colour at render time.

alter table outfit_templates
    add column if not exists mask2_url text,
    add column if not exists mask2_region text,
    add column if not exists mask3_url text,
    add column if not exists mask3_region text;

comment on column outfit_templates.mask2_url is
    'Optional mask for the 2nd garment (trousers, choli, pajama...). Null = one-piece.';
comment on column outfit_templates.mask3_url is
    'Optional mask for the 3rd garment (waistcoat...). Null = fewer than 3 pieces.';
