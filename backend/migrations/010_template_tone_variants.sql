-- 010: map canonical skin tones to public template image URLs.
-- Example: {"fair":"https://...","dusky":"https://..."}
-- Garment masks remain shared because non-skin pixels use the same geometry.
-- Safe to run repeatedly in the Supabase SQL Editor.

alter table public.outfit_templates
    add column if not exists tone_variants jsonb not null default '{}'::jsonb;

comment on column public.outfit_templates.tone_variants is
    'Public template image URLs keyed by fair, light, wheatish, medium, dusky, deep, warm, and cool';

select pg_notify('pgrst', 'reload schema');