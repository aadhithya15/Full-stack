-- HueFit migration 003: user-selected style catalogue fields
-- Run once in Supabase SQL Editor after 001_init.sql.
-- Safe to run repeatedly.

alter table public.analyses
  add column if not exists dress_type text,
  add column if not exists preferred_material text;

alter table public.recommendations
  add column if not exists outfit_type text,
  add column if not exists materials jsonb not null default '[]'::jsonb;
