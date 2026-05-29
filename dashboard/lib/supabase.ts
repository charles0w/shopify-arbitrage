import { createClient } from "@supabase/supabase-js";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyClient = ReturnType<typeof createClient<any>>;

let _client: AnyClient | null = null;

export function getSupabase(): AnyClient {
  if (!_client) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    _client = createClient<any>(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_KEY!
    );
  }
  return _client;
}

export type QueueItem = {
  id: string;
  date: string;
  cj_product_id: string;
  title: string;
  supplier_price_usd: number;
  suggested_sale_price_usd: number;
  score: number;
  keyword: string;
  product_url: string;
  image_url: string;
  image_urls: string[] | null;
  listing_title: string | null;
  listing_body_html: string | null;
  listing_tags: string[] | null;
  listing_meta_title: string | null;
  listing_meta_description: string | null;
  status: "pending" | "approved" | "rejected";
  shopify_product_id: string | null;
  created_at: string;
};

export type Fulfillment = {
  id: string;
  shopify_order_id: string;
  shopify_order_name: string;
  shopify_order_total: number;
  cj_order_id: string | null;
  tracking_number: string | null;
  carrier: string | null;
  status: "pending" | "cj_pending" | "cj_placed" | "shipped" | "error";
  error_message: string | null;
  created_at: string;
  updated_at: string;
};
