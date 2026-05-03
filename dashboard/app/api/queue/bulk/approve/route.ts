import { NextRequest, NextResponse } from "next/server";
import { getSupabase, type QueueItem } from "@/lib/supabase";
import { createDraft } from "@/lib/shopify";

export const dynamic = "force-dynamic";
// Sequential createDraft calls + per-item Supabase update can take several
// seconds for a large batch. Default Vercel timeout is 10s — bump it.
export const maxDuration = 60;

const UPDATE_BACKOFF_MS = [500, 1500, 4000];

type ItemResult =
  | { id: string; ok: true; shopify_product_id: string }
  | { id: string; ok: false; error: string };

export async function POST(req: NextRequest) {
  let body: { ids?: string[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const ids = Array.isArray(body.ids) ? body.ids : [];
  if (ids.length === 0) {
    return NextResponse.json({ error: "ids required" }, { status: 400 });
  }
  if (ids.length > 50) {
    return NextResponse.json(
      { error: "Max 50 items per bulk approve — split into smaller batches" },
      { status: 400 }
    );
  }

  const sb = getSupabase();

  // Fetch all rows in one query, filter to pending
  const { data, error: fetchErr } = await sb
    .from("queue_items")
    .select("*")
    .in("id", ids);
  if (fetchErr) {
    return NextResponse.json({ error: fetchErr.message }, { status: 500 });
  }
  const itemsById = new Map(((data || []) as QueueItem[]).map((i) => [i.id, i]));

  // Process serially to stay well within Shopify's 2-req/sec REST budget
  // and to keep error attribution clean per item.
  const results: ItemResult[] = [];
  for (const id of ids) {
    const item = itemsById.get(id);
    if (!item) {
      results.push({ id, ok: false, error: "Not found" });
      continue;
    }
    if (item.status !== "pending") {
      results.push({ id, ok: false, error: `Already ${item.status}` });
      continue;
    }

    let shopifyProductId: string;
    try {
      const product = await createDraft(item);
      shopifyProductId = String(product.id);
    } catch (err: unknown) {
      results.push({
        id,
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
      continue;
    }

    // Same retry-on-update pattern as the single-id approve (PR #9)
    let updateErr: string | null = null;
    for (let attempt = 0; attempt <= UPDATE_BACKOFF_MS.length; attempt++) {
      const { error } = await sb
        .from("queue_items")
        .update({ status: "approved", shopify_product_id: shopifyProductId })
        .eq("id", id);
      if (!error) {
        updateErr = null;
        break;
      }
      updateErr = error.message;
      if (attempt < UPDATE_BACKOFF_MS.length) {
        await new Promise((r) => setTimeout(r, UPDATE_BACKOFF_MS[attempt]));
      }
    }

    if (updateErr) {
      // Same orphan-recovery shape as the single approve route — Shopify
      // product exists, Supabase is stale. Caller surfaces the
      // shopify_product_id so the operator can patch.
      results.push({
        id,
        ok: false,
        error:
          `Shopify product ${shopifyProductId} created but Supabase update failed ` +
          `after ${UPDATE_BACKOFF_MS.length + 1} attempts: ${updateErr}. ` +
          `Patch queue_items.status='approved' and shopify_product_id=${shopifyProductId} ` +
          `manually, or delete the Shopify product to retry.`,
      });
      continue;
    }

    results.push({ id, ok: true, shopify_product_id: shopifyProductId });
  }

  const approved = results.filter((r) => r.ok).length;
  const failed = results.length - approved;
  return NextResponse.json({ approved, failed, results });
}
