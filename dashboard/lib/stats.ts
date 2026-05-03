import { getProductCount, getOrderCount } from "@/lib/shopify";
import { getSupabase } from "@/lib/supabase";

export type DailyPoint = { date: string; total: number };

export type Stats = {
  products: number;
  orders: number;
  pending_queue: number;
  revenue_30d: number;
  daily_revenue_14d: DailyPoint[];
};

const DAILY_WINDOW = 14;

export async function getStats(): Promise<Stats> {
  const today = new Date().toISOString().split("T")[0];
  const sb = getSupabase();
  const since30 = new Date(Date.now() - 30 * 86400 * 1000).toISOString();
  const since14 = new Date(Date.now() - DAILY_WINDOW * 86400 * 1000).toISOString();

  const [
    products,
    orders,
    { data: queueItems },
    { data: orders30 },
    { data: orders14 },
  ] = await Promise.all([
    getProductCount(),
    getOrderCount(),
    sb.from("queue_items").select("status").eq("date", today),
    sb.from("fulfillments").select("shopify_order_total").gte("created_at", since30),
    sb
      .from("fulfillments")
      .select("shopify_order_total, created_at")
      .gte("created_at", since14),
  ]);

  const pending_queue = (queueItems || []).filter(
    (q: { status: string }) => q.status === "pending"
  ).length;

  const revenue_30d = (orders30 || []).reduce(
    (sum: number, r: { shopify_order_total: number | null }) =>
      sum + (r.shopify_order_total || 0),
    0
  );

  const daily_revenue_14d = bucketByDay(
    (orders14 || []) as { shopify_order_total: number | null; created_at: string }[],
    DAILY_WINDOW
  );

  return { products, orders, pending_queue, revenue_30d, daily_revenue_14d };
}

/**
 * Group fulfillment rows into one bucket per day for the last `windowDays`,
 * filling zeros for days with no orders so the sparkline keeps a consistent
 * X-axis. Most recent day last.
 */
function bucketByDay(
  rows: { shopify_order_total: number | null; created_at: string }[],
  windowDays: number
): DailyPoint[] {
  const buckets = new Map<string, number>();
  const today = new Date();
  for (let i = windowDays - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400 * 1000)
      .toISOString()
      .split("T")[0];
    buckets.set(d, 0);
  }
  for (const row of rows) {
    const day = (row.created_at || "").split("T")[0];
    if (buckets.has(day)) {
      buckets.set(day, (buckets.get(day) || 0) + (row.shopify_order_total || 0));
    }
  }
  return Array.from(buckets.entries()).map(([date, total]) => ({ date, total }));
}
