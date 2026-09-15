-- 010: map approved native skin tones to public template image URLs.
-- Garment masks remain shared because every complexion keeps the same geometry.
-- Safe to run repeatedly in the Supabase SQL Editor.

alter table public.outfit_templates
    add column if not exists tone_variants jsonb not null default '{}'::jsonb;

comment on column public.outfit_templates.tone_variants is
    'Public template image URLs keyed by as-shot, light-warm, light-tan, medium-brown, deep, and ebony';

select pg_notify('pgrst', 'reload schema');
