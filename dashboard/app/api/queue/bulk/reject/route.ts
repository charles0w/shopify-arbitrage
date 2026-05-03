import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

/**
 * Bulk-reject queue items.
 *
 * Reject is just a Supabase status update with no Shopify side effect, so
 * the whole batch goes in a single .in().update() call rather than the
 * serial loop bulk approve uses. Already-approved or already-rejected rows
 * are silently passed over by the eq filter on status='pending' — caller
 * sees `rejected` reflect only what actually transitioned.
 */
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
  if (ids.length > 200) {
    return NextResponse.json(
      { error: "Max 200 ids per request" },
      { status: 400 }
    );
  }

  const sb = getSupabase();
  const { data, error } = await sb
    .from("queue_items")
    .update({ status: "rejected" })
    .in("id", ids)
    .eq("status", "pending")
    .select("id");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  const rejected = (data || []).length;
  return NextResponse.json({
    rejected,
    skipped: ids.length - rejected,
  });
}
