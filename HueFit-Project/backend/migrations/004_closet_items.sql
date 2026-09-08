-- HueFit migration 004: private digital closet items
-- Run once in Supabase SQL Editor after the previous migrations.

create table if not exists public.closet_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  item_name text not null,
  item_type text not null,
  colour text,
  material text,
  image_path text,
  created_at timestamptz not null default now()
);

create index if not exists idx_closet_items_user
  on public.closet_items (user_id, created_at desc);

alter table public.closet_items enable row level security;

drop policy if exists "own closet items" on public.closet_items;
create policy "own closet items" on public.closet_items
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
