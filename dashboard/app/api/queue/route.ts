import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const date =
    req.nextUrl.searchParams.get("date") ||
    new Date().toISOString().split("T")[0];

  const { data, error } = await getSupabase()
    .from("queue_items")
    .select("*")
    .eq("date", date)
    .order("score", { ascending: false });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
