-- ============================================================
-- HueFit â€” Migration 001: initial schema
-- Run this ONCE in: Supabase Dashboard â†’ SQL Editor â†’ New query
-- Paste the whole file â†’ Run. Expect: "Success. No rows returned"
-- ============================================================
-- Users themselves live in auth.users (managed by Supabase Auth).
-- These tables hold everything else, all linked by user id.

-- ---------- 1) profiles â€” extended user details ----------
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  gender text check (gender in ('male', 'female', 'neutral')),
  skin_tone text,                          -- last known/declared tone e.g. 'warm', 'wheatish', 'dusky'
  style_preference text check (style_preference in ('traditional', 'western', 'formal', 'casual', 'any')),
  default_budget text check (default_budget in ('low', 'medium', 'premium')),
  language text not null default 'en',     -- future: en / ta / hi
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------- 2) analyses â€” every analyze request ----------
create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  input_type text not null check (input_type in ('photo', 'text')),
  skin_tone_input text,                    -- what the user typed (text flow)
  detected_skin_tone text,                 -- vision/model result (photo flow) or normalized text
  photo_url text,                          -- storage path if a photo was uploaded
  occasion text not null,
  gender text,
  style_preference text,
  budget text,
  season_weather text,
  notes text,
  created_at timestamptz not null default now()
);

-- ---------- 3) recommendations â€” AI outfits (3â€“5 per analysis) ----------
create table if not exists public.recommendations (
  id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  outfit_name text not null,
  category text,                           -- traditional / western / formal / casual / fusion
  description text,
  dress_colors jsonb not null default '[]'::jsonb,   -- [{"name":"Emerald Green","hex":"#0F7B4D"}, ...]
  accessories jsonb not null default '[]'::jsonb,    -- ["gold jhumkas", ...]
  footwear text,
  styling_tips text,
  avoid_colors jsonb not null default '[]'::jsonb,
  image_url text,                          -- Pollinations URL (or null)
  match_score numeric check (match_score >= 0 and match_score <= 100),
  is_mock boolean not null default false,  -- true while AI keys were placeholders
  created_at timestamptz not null default now()
);

-- ---------- 4) saved_looks â€” wardrobe / favourites ----------
create table if not exists public.saved_looks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  recommendation_id uuid not null references public.recommendations(id) on delete cascade,
  is_favourite boolean not null default false,
  saved_at timestamptz not null default now(),
  unique (user_id, recommendation_id)      -- can't save the same look twice
);

-- ---------- Indexes ----------
create index if not exists idx_analyses_user on public.analyses (user_id, created_at desc);
create index if not exists idx_reco_analysis on public.recommendations (analysis_id);
create index if not exists idx_reco_user on public.recommendations (user_id, created_at desc);
create index if not exists idx_saved_user on public.saved_looks (user_id, saved_at desc);

-- ---------- updated_at trigger for profiles ----------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ---------- Auto-create a profile row when a user registers ----------
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists trg_on_auth_user_created on auth.users;
create trigger trg_on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- Row Level Security ----------
-- Our Flask backend uses the service_role key (bypasses RLS) and enforces
-- ownership in queries. RLS is enabled anyway as defense in depth, so the
-- public anon key can never read anyone's data directly.
alter table public.profiles enable row level security;
alter table public.analyses enable row level security;
alter table public.recommendations enable row level security;
alter table public.saved_looks enable row level security;

drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "own analyses" on public.analyses;
create policy "own analyses" on public.analyses
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own recommendations" on public.recommendations;
create policy "own recommendations" on public.recommendations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own saved looks" on public.saved_looks;
create policy "own saved looks" on public.saved_looks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ============================================================
-- Done. Verify in Table Editor: profiles, analyses,
-- recommendations, saved_looks should all appear.
-- ============================================================
