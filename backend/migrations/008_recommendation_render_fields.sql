-- 008: columns for the MVP template-recolouring pipeline.
-- Each saved recommendation records how its image was produced.

alter table recommendations
    add column if not exists image_source text not null default 'none',
    add column if not exists template_code text;

comment on column recommendations.image_source is
    'How image_url was produced: template (recoloured outfit template) or none';
comment on column recommendations.template_code is
    'outfit_templates.template_code used for the render, null when image_source = none';
