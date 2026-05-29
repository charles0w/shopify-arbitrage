-- Run this in your Supabase SQL editor to set up the schema.

create table if not exists queue_items (
  id                       uuid default gen_random_uuid() primary key,
  date                     date not null,
  cj_product_id            text not null,
  title                    text,
  supplier_price_usd       numeric,
  suggested_sale_price_usd numeric,
  score                    numeric,
  keyword                  text,
  product_url              text,
  image_url                text,
  image_urls               text[],
  listing_title            text,
  listing_body_html        text,
  listing_tags             text[],
  listing_meta_title       text,
  listing_meta_description text,
  status                   text default 'pending' check (status in ('pending', 'approved', 'rejected')),
  shopify_product_id       text,
  created_at               timestamptz default now()
);

create index if not exists queue_items_date_idx on queue_items (date);

create table if not exists fulfillments (
  id                   uuid default gen_random_uuid() primary key,
  shopify_order_id     text not null unique,
  shopify_order_name   text,
  shopify_order_total  numeric,
  cj_order_id          text,
  tracking_number      text,
  carrier              text,
  status               text default 'pending' check (status in ('pending', 'cj_pending', 'cj_placed', 'shipped', 'error')),
  error_message        text,
  created_at           timestamptz default now(),
  updated_at           timestamptz default now()
);

create index if not exists fulfillments_status_idx on fulfillments (status);

-- Migration: if you set up the schema before 'cj_pending' was added, run this
-- to relax the status check. Safe to re-run.
do $$
begin
  if exists (
    select 1 from information_schema.constraint_column_usage
    where constraint_name = 'fulfillments_status_check'
  ) then
    alter table fulfillments drop constraint fulfillments_status_check;
  end if;
  alter table fulfillments add constraint fulfillments_status_check
    check (status in ('pending', 'cj_pending', 'cj_placed', 'shipped', 'error'));
end $$;

-- Migration: add image_urls (text[]) to queue_items if missing.
alter table queue_items add column if not exists image_urls text[];
