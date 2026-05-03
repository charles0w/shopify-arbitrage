export const dynamic = "force-dynamic";

import { getStats } from "@/lib/stats";
import Sparkline from "@/components/Sparkline";

export default async function StatsPage() {
  const stats = await getStats();

  const dailyMax = Math.max(...stats.daily_revenue_14d.map((d) => d.total), 0);
  const dailyTotal = stats.daily_revenue_14d.reduce((s, d) => s + d.total, 0);
  const dailyAvg = dailyTotal / Math.max(stats.daily_revenue_14d.length, 1);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-zinc-100">Overview</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Store snapshot — live products, orders, and 30-day revenue
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <StatCard label="Live Products" value={stats.products} />
        <StatCard label="Paid Orders" value={stats.orders} />
        <StatCard
          label="Pending Today"
          value={stats.pending_queue}
          highlight={stats.pending_queue > 0}
        />
        <StatCard label="Revenue (30d)" value={`$${stats.revenue_30d.toFixed(2)}`} />
      </div>

      {/* Daily revenue trend — only render when there's actually data so a
          fresh deploy doesn't show 14 days of zero. */}
      {dailyMax > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4">
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-xs text-zinc-500 font-medium uppercase tracking-wide">
              Revenue · last 14 days
            </p>
            <p className="text-xs text-zinc-500 tabular-nums">
              avg ${dailyAvg.toFixed(2)}/day · peak ${dailyMax.toFixed(2)}
            </p>
          </div>
          <Sparkline
            data={stats.daily_revenue_14d}
            ariaLabel="Daily revenue over the last 14 days"
          />
          <div className="flex justify-between text-[10px] text-zinc-600 mt-2 tabular-nums">
            <span>{stats.daily_revenue_14d[0]?.date}</span>
            <span>{stats.daily_revenue_14d.at(-1)?.date}</span>
          </div>
        </div>
      )}
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
