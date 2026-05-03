import type { QueueItem } from "./supabase";

const BASE = `https://${process.env.SHOPIFY_STORE_URL}/admin/api/2024-01`;

const headers = () => ({
  "X-Shopify-Access-Token": process.env.SHOPIFY_ACCESS_TOKEN!,
  "Content-Type": "application/json",
});

export async function getOrders(limit = 50): Promise<ShopifyOrder[]> {
  try {
    const resp = await fetch(
      `${BASE}/orders.json?limit=${limit}&status=any&order=created_at+desc`,
      { headers: headers(), next: { revalidate: 60 } }
    );
    if (!resp.ok) {
      console.warn(`[shopify] getOrders ${resp.status}`);
      return [];
    }
    return (await resp.json()).orders as ShopifyOrder[];
  } catch (e) {
    console.warn(`[shopify] getOrders failed:`, e);
    return [];
  }
}

export async function getProductCount(): Promise<number> {
  try {
    const resp = await fetch(`${BASE}/products/count.json?status=active`, {
      headers: headers(),
      next: { revalidate: 300 },
    });
    if (!resp.ok) return 0;
    return (await resp.json()).count as number;
  } catch {
    return 0;
  }
}

export async function getOrderCount(): Promise<number> {
  try {
    const resp = await fetch(
      `${BASE}/orders/count.json?financial_status=paid`,
      { headers: headers(), next: { revalidate: 60 } }
    );
    if (!resp.ok) return 0;
    return (await resp.json()).count as number;
  } catch {
    return 0;
  }
}

export async function createDraft(item: QueueItem) {
  const payload = {
    product: {
      title: item.listing_title || item.title,
      body_html: item.listing_body_html || "",
      tags: (item.listing_tags || []).join(", "),
      status: "draft",
      variants: [
        {
          price: item.suggested_sale_price_usd.toFixed(2),
          requires_shipping: true,
          taxable: true,
          inventory_management: null,
        },
      ],
      images: item.image_url ? [{ src: item.image_url }] : [],
      metafields: [
        {
          namespace: "arbitrage",
          key: "supplier_url",
          value: item.product_url || "",
          type: "url",
        },
        {
          namespace: "arbitrage",
          key: "supplier_price",
          value: String(item.supplier_price_usd),
          type: "single_line_text_field",
        },
        {
          // Recovery key: if a Supabase update fails after this product is
          // created, we can find the orphan by filtering Shopify products on
          // this metafield and reconcile manually.
          namespace: "arbitrage",
          key: "queue_item_id",
          value: item.id,
          type: "single_line_text_field",
        },
      ],
    },
  };

  const resp = await fetch(`${BASE}/products.json`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Shopify ${resp.status}: ${err}`);
  }
  return (await resp.json()).product as { id: number };
}

export type ShopifyOrder = {
  id: number;
  name: string;
  created_at: string;
  financial_status: string;
  fulfillment_status: string | null;
  total_price: string;
  line_items: { title: string; quantity: number; price: string }[];
  shipping_address?: { name: string };
  customer?: { first_name: string; last_name: string; email: string };
};
