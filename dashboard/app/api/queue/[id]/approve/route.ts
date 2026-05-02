import { NextRequest, NextResponse } from "next/server";
import { getSupabase, type QueueItem } from "@/lib/supabase";
import { createDraft } from "@/lib/shopify";

export const dynamic = "force-dynamic";

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const sb = getSupabase();

  const { data, error: fetchErr } = await sb
    .from("queue_items")
    .select("*")
    .eq("id", params.id)
    .single();

  const item = data as QueueItem | null;

  if (fetchErr || !item) {
    return NextResponse.json({ error: "Item not found" }, { status: 404 });
  }

  if (item.status !== "pending") {
    return NextResponse.json({ error: `Already ${item.status}` }, { status: 400 });
  }

  try {
    const product = await createDraft(item);
    const { error: updateErr } = await sb
      .from("queue_items")
      .update({ status: "approved", shopify_product_id: String(product.id) })
      .eq("id", params.id);

    if (updateErr) throw new Error(updateErr.message);
    return NextResponse.json({ shopify_product_id: product.id });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
