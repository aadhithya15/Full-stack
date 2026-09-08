-- HueFit migration 002: structured garment details

alter table public.recommendations
  add column if not exists garments jsonb not null default '[]'::jsonb;

select pg_notify('pgrst', 'reload schema');