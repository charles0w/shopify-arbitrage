import { NextResponse } from "next/server";
import { getOrders } from "@/lib/shopify";
import { getSupabase, type Fulfillment } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET() {
  const [orders, { data: fulfillments }] = await Promise.all([
    getOrders(50),
    getSupabase().from("fulfillments").select("*"),
  ]);

  const fMap = new Map(
    ((fulfillments || []) as Fulfillment[]).map((f) => [f.shopify_order_id, f])
  );

  const merged = orders.map((o) => ({
    ...o,
    fulfillment: fMap.get(String(o.id)) ?? null,
  }));

  return NextResponse.json(merged);
}
