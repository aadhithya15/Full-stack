-- Clear ages outside the new 14-45 band (old test data)
update public.analyses
  set age = null
  where age is not null and (age < 14 or age > 45);

-- Now apply the new constraint
alter table public.analyses
  drop constraint if exists analyses_age_check;

alter table public.analyses
  add constraint analyses_age_check check (age between 14 and 45);

select pg_notify('pgrst', 'reload schema');