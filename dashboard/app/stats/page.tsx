export const dynamic = "force-dynamic";

import { getStats } from "@/lib/stats";

export default async function StatsPage() {
  const stats = await getStats();

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-zinc-100">Overview</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Store snapshot — live products, orders, and 30-day revenue
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Live Products" value={stats.products} />
        <StatCard label="Paid Orders" value={stats.orders} />
        <StatCard
          label="Pending Today"
          value={stats.pending_queue}
          highlight={stats.pending_queue > 0}
        />
        <StatCard label="Revenue (30d)" value={`$${stats.revenue_30d.toFixed(2)}`} />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number | string;
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
