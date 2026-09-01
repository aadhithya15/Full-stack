-- HueFit migration 006b: the vector-search function for the v2 engine
-- Run AFTER 006_products.sql, once, in the Supabase SQL Editor.
-- Safe to run repeatedly (create or replace).
--
-- Why a function: the nearest-neighbour comparison must run INSIDE the
-- database so the HNSW index is used (milliseconds even at 100K products).
-- The backend calls it via supabase.rpc('match_products', {...}).

create or replace function public.match_products(
  query_embedding vector(512),
  match_count int default 15,
  filter_gender text default null,
  filter_culture text default null,
  filter_occasion text default null
)
returns table (
  id uuid,
  title text,
  gender text,
  dress_type text,
  culture text,
  occasions text[],
  dominant_hex text,
  hue_family text,
  tags text[],
  price numeric,
  currency text,
  image_url text,
  buy_url text,
  similarity float
)
language sql stable as $$
  select
    p.id, p.title, p.gender, p.dress_type, p.culture, p.occasions,
    p.dominant_hex, p.hue_family, p.tags, p.price, p.currency,
    p.image_url, p.buy_url,
    1 - (p.embedding <=> query_embedding) as similarity
  from public.products p
  where p.embedding is not null
    and p.in_stock = true
    and (filter_gender is null or p.gender = filter_gender or p.gender = 'unisex')
    and (filter_culture is null or p.culture = filter_culture)
    and (filter_occasion is null or filter_occasion = any(p.occasions))
  order by p.embedding <=> query_embedding
  limit match_count;
$$;

select pg_notify('pgrst', 'reload schema');
