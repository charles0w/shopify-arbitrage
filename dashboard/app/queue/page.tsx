export const dynamic = "force-dynamic";

import { getSupabase } from "@/lib/supabase";
import type { QueueItem } from "@/lib/supabase";
import QueueGrid from "@/components/QueueGrid";
import { getProductCount, getOrderCount } from "@/lib/shopify";

async function getStats(today: string) {
  const [products, orders, { data: queueItems }] = await Promise.all([
    getProductCount(),
    getOrderCount(),
    getSupabase().from("queue_items").select("status").eq("date", today),
  ]);
  const pending = (queueItems || []).filter((q) => q.status === "pending").length;
  return { products, orders, pending };
}

async function getQueue(date: string): Promise<QueueItem[]> {
  const { data } = await getSupabase()
    .from("queue_items")
    .select("*")
    .eq("date", date)
    .order("score", { ascending: false });
  return (data || []) as QueueItem[];
}

export default async function QueuePage({
  searchParams,
}: {
  searchParams: { date?: string };
}) {
  const today = new Date().toISOString().split("T")[0];
  const date = searchParams.date || today;
  const [stats, items] = await Promise.all([getStats(today), getQueue(date)]);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Product Queue</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Review and approve products for your store
          </p>
        </div>
        <form method="GET">
          <input
            type="date"
            name="date"
            defaultValue={date}
            className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-indigo-500"
          />
        </form>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Live Products" value={stats.products} />
        <StatCard label="Total Orders" value={stats.orders} />
        <StatCard
          label="Pending Today"
          value={stats.pending}
          highlight={stats.pending > 0}
        />
      </div>

      {/* Queue */}
      <QueueGrid items={items} />
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4">
      <p className="text-xs text-zinc-500 font-medium uppercase tracking-wide">
        {label}
      </p>
      <p
        className={`text-3xl font-semibold mt-1 tabular-nums ${
          highlight ? "text-indigo-400" : "text-zinc-100"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
