import { getProductCount, getOrderCount } from "@/lib/shopify";
import { getSupabase } from "@/lib/supabase";

export type Stats = {
  products: number;
  orders: number;
  pending_queue: number;
  revenue_30d: number;
};

export async function getStats(): Promise<Stats> {
  const today = new Date().toISOString().split("T")[0];
  const sb = getSupabase();
  const since = new Date(Date.now() - 30 * 86400 * 1000).toISOString();

  const [products, orders, { data: queueItems }, { data: recentOrders }] =
    await Promise.all([
      getProductCount(),
      getOrderCount(),
      sb.from("queue_items").select("status").eq("date", today),
      sb.from("fulfillments").select("shopify_order_total").gte("created_at", since),
    ]);

  const pending_queue = (queueItems || []).filter(
    (q: { status: string }) => q.status === "pending"
  ).length;
  const revenue_30d = (recentOrders || []).reduce(
    (sum: number, r: { shopify_order_total: number | null }) =>
      sum + (r.shopify_order_total || 0),
    0
  );

  return { products, orders, pending_queue, revenue_30d };
}
