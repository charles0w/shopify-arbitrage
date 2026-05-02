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
  status               text default 'pending' check (status in ('pending', 'cj_placed', 'shipped', 'error')),
  error_message        text,
  created_at           timestamptz default now(),
  updated_at           timestamptz default now()
);

create index if not exists fulfillments_status_idx on fulfillments (status);
