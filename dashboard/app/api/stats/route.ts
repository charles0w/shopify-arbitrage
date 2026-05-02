import { NextResponse } from "next/server";
import { getProductCount, getOrderCount } from "@/lib/shopify";
import { getSupabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET() {
  const today = new Date().toISOString().split("T")[0];
  const sb = getSupabase();

  const [products, orders, { data: queueItems }, { data: recentOrders }] =
    await Promise.all([
      getProductCount(),
      getOrderCount(),
      sb.from("queue_items").select("status").eq("date", today),
      sb
        .from("fulfillments")
        .select("shopify_order_total")
        .gte("created_at", new Date(Date.now() - 30 * 86400 * 1000).toISOString()),
    ]);

  const pending = (queueItems || []).filter((q) => q.status === "pending").length;
  const revenue = (recentOrders || []).reduce(
    (sum, r) => sum + (r.shopify_order_total || 0),
    0
  );

  return NextResponse.json({ products, orders, pending_queue: pending, revenue_30d: revenue });
}
