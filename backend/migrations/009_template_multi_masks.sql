-- 009: support up to three independently recolourable garment masks.
-- Safe to run repeatedly in the Supabase SQL Editor.

alter table public.outfit_templates
    add column if not exists mask2_url text,
    add column if not exists mask3_url text;

comment on column public.outfit_templates.mask2_url is
    'Optional second QA-approved garment mask stored in the public templates bucket';
comment on column public.outfit_templates.mask3_url is
    'Optional third QA-approved garment mask stored in the public templates bucket';

select pg_notify('pgrst', 'reload schema');