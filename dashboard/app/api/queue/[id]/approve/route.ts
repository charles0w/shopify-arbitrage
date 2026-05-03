import { NextRequest, NextResponse } from "next/server";
import { getSupabase, type QueueItem } from "@/lib/supabase";
import { createDraft } from "@/lib/shopify";

export const dynamic = "force-dynamic";

const UPDATE_BACKOFF_MS = [500, 1500, 4000];

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

  let product: { id: number };
  try {
    product = await createDraft(item);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }

  // Shopify product exists. Updating Supabase MUST eventually succeed or the
  // operator will see a stale "pending" row and may click Approve again,
  // creating a duplicate. Retry on transient failure; if we exhaust retries,
  // return the orphaned shopify_product_id so the operator can patch the row
  // manually instead of clicking Approve again.
  const productId = String(product.id);
  let lastErr: string | null = null;
  for (let attempt = 0; attempt <= UPDATE_BACKOFF_MS.length; attempt++) {
    const { error: updateErr } = await sb
      .from("queue_items")
      .update({ status: "approved", shopify_product_id: productId })
      .eq("id", params.id);

    if (!updateErr) {
      return NextResponse.json({ shopify_product_id: product.id });
    }

    lastErr = updateErr.message;
    if (attempt < UPDATE_BACKOFF_MS.length) {
      await new Promise((r) => setTimeout(r, UPDATE_BACKOFF_MS[attempt]));
    }
  }

  return NextResponse.json(
    {
      error:
        `Shopify product was created (id ${productId}) but Supabase update ` +
        `failed after ${UPDATE_BACKOFF_MS.length + 1} attempts: ${lastErr}. ` +
        `Manually set queue_items.shopify_product_id and status='approved' ` +
        `for queue item ${params.id} to recover (or delete the Shopify ` +
        `product to retry).`,
      shopify_product_id: productId,
      queue_item_id: params.id,
    },
    { status: 500 }
  );
}
