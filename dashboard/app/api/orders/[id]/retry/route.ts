import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

/**
 * Clear an errored fulfillment so the next cron tick re-attempts it.
 *
 * Stateless workers (GitHub Actions) reconstruct fulfilled_order_ids by
 * pulling Supabase rows in _load_state(); deleting the row here drops the
 * Shopify order from that set, and the next get_new_orders() poll will
 * pick it up again.
 */
export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const sb = getSupabase();
  const { data, error: fetchErr } = await sb
    .from("fulfillments")
    .select("status")
    .eq("shopify_order_id", params.id)
    .single();

  if (fetchErr || !data) {
    return NextResponse.json(
      { error: "Fulfillment record not found" },
      { status: 404 }
    );
  }
  if (data.status !== "error") {
    return NextResponse.json(
      { error: `Cannot retry — status is ${data.status}` },
      { status: 400 }
    );
  }

  const { error: delErr } = await sb
    .from("fulfillments")
    .delete()
    .eq("shopify_order_id", params.id);

  if (delErr) {
    return NextResponse.json({ error: delErr.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
