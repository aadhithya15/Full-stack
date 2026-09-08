-- HueFit migration 006: v2 retrieval engine - product catalogue with vectors
-- Run once in the Supabase SQL Editor. Safe to run repeatedly.
--
-- Requires the pgvector extension (bundled with Supabase, just enable it).

create extension if not exists vector;

-- ---------- clients: which shop/catalogue a product belongs to ----------
create table if not exists public.catalog_clients (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,           -- e.g. 'starter', 'boutique-abc'
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

-- ---------- products: one row per real, buyable item ----------
create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.catalog_clients(id) on delete cascade,
  title text not null,
  gender text not null check (gender in ('male', 'female', 'unisex')),
  dress_type text not null,            -- our catalog values e.g. 'saree', 'blazer-trousers'
  culture text not null default 'western'
    check (culture in ('tamil', 'western', 'fusion')),
  occasions text[] not null default '{}',        -- e.g. {festive, wedding}
  dominant_hex text,                   -- '#973922'
  hue_family text,                     -- 'maroon-red' (drives the colour law)
  tags text[] not null default '{}',   -- {silk, zari, traditional}
  price numeric(10,2),
  currency text not null default 'INR',
  image_url text not null,             -- permanent public-bucket or client link
  buy_url text,
  in_stock boolean not null default true,
  embedding vector(512),               -- CLIP map coordinates (null until indexed)
  indexed_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------- indexes ----------
-- HNSW: millisecond nearest-neighbour search on the embedding
create index if not exists idx_products_embedding
  on public.products using hnsw (embedding vector_cosine_ops);

create index if not exists idx_products_client on public.products (client_id);
create index if not exists idx_products_gender_stock on public.products (gender, in_stock);
create index if not exists idx_products_culture on public.products (culture);

-- ---------- Row Level Security ----------
-- The backend uses the service key (bypasses RLS); these policies are the
-- defence-in-depth layer. Catalogue data is world-READABLE (it is public
-- marketing material) but never writable via the anon key.
alter table public.products enable row level security;
alter table public.catalog_clients enable row level security;

drop policy if exists "products are public to read" on public.products;
create policy "products are public to read" on public.products
  for select using (true);

drop policy if exists "clients are public to read" on public.catalog_clients;
create policy "clients are public to read" on public.catalog_clients
  for select using (true);

-- (no insert/update/delete policies for anon: only the service key writes)

select pg_notify('pgrst', 'reload schema');
