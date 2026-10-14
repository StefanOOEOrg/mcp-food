create extension if not exists pg_trgm;
create extension if not exists unaccent;
create schema if not exists food;

create table if not exists food.items (
  id            serial primary key,
  source        text not null check (source in ('my', 'off', 'bls')),
  source_ref    text not null,
  name          text not null,
  brand         text,
  kcal_100g     numeric,
  protein_100g  numeric,
  carbs_100g    numeric,
  fat_100g      numeric,
  fiber_100g    numeric,
  sugar_100g    numeric,
  satfat_100g   numeric,
  salt_100g     numeric,
  alcohol_100g  numeric,
  serving_g     numeric,
  serving_desc  text,
  -- nutrition per serving when only that is known (MFP history without grams)
  kcal_serving    numeric,
  protein_serving numeric,
  carbs_serving   numeric,
  fat_serving     numeric,
  uses          integer not null default 0,
  updated_at    timestamptz not null default now(),
  unique (source, source_ref)
);
create index if not exists items_name_trgm on food.items using gin (lower(name) gin_trgm_ops);

create table if not exists food.recipes (
  id             serial primary key,
  name           text not null unique,
  portions       numeric not null default 1,
  total_weight_g numeric,
  notes          text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create table if not exists food.recipe_items (
  recipe_id integer not null references food.recipes(id) on delete cascade,
  item_id   integer not null references food.items(id),
  grams     numeric not null check (grams > 0),
  primary key (recipe_id, item_id)
);
