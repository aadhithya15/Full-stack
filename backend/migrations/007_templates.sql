-- HueFit migration 007: outfit template library (MVP recolouring approach)
-- Implements the "Reusable Template Masking Strategy" document, section 8.
-- Run once in the Supabase SQL Editor. Safe to run repeatedly.
--
-- One row = one approved outfit template + its QA-approved garment mask.
-- The mask belongs to the TEMPLATE (not the user): created once, QA'd once,
-- reused for every request that selects this template.

create table if not exists public.outfit_templates (
  id uuid primary key default gen_random_uuid(),
  template_code text not null unique,      -- human id e.g. 'saree_f_01'
  dress_type text not null,                -- catalog value: saree, kurta-pajama...
  gender text not null check (gender in ('male', 'female', 'unisex')),
  culture text not null default 'tamil'
    check (culture in ('tamil', 'western', 'fusion')),
  style_tags text[] not null default '{}', -- {traditional, modern, fusion, festive...}
  image_url text not null,                 -- original template image (public bucket)
  mask_url text not null,                  -- QA-approved garment mask PNG
  mask_region text not null default 'full-garment',  -- which garment area the mask covers
  base_hue_family text,                    -- template's own colour family (recolour hint)
  qa_status text not null default 'pending'
    check (qa_status in ('pending', 'approved', 'needs-correction')),
  active_status boolean not null default false,  -- only true+approved are selectable
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- selection lookups: dress type + gender + active
create index if not exists idx_templates_selection
  on public.outfit_templates (dress_type, gender, active_status);

create index if not exists idx_templates_culture
  on public.outfit_templates (culture);

-- reuse the shared updated_at trigger from migration 001
drop trigger if exists trg_templates_updated_at on public.outfit_templates;
create trigger trg_templates_updated_at
  before update on public.outfit_templates
  for each row execute function public.set_updated_at();

-- RLS: world-readable (templates are public assets), service-key writes only
alter table public.outfit_templates enable row level security;

drop policy if exists "templates are public to read" on public.outfit_templates;
create policy "templates are public to read" on public.outfit_templates
  for select using (true);

select pg_notify('pgrst', 'reload schema');
