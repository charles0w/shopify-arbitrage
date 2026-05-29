export const dynamic = "force-dynamic";

import { getOrders } from "@/lib/shopify";
import { getSupabase } from "@/lib/supabase";
import type { Fulfillment } from "@/lib/supabase";
import type { ShopifyOrder } from "@/lib/shopify";
import OrdersTable from "@/components/OrdersTable";

type MergedOrder = ShopifyOrder & { fulfillment: Fulfillment | null };

async function getOrdersWithFulfillment(): Promise<MergedOrder[]> {
  const [orders, { data: fulfillments }] = await Promise.all([
    getOrders(50),
    getSupabase().from("fulfillments").select("*"),
  ]);
  const fMap = new Map(
    (fulfillments || []).map((f: Fulfillment) => [f.shopify_order_id, f])
  );
  return orders.map((o) => ({ ...o, fulfillment: fMap.get(String(o.id)) ?? null }));
}

export default async function OrdersPage() {
  const orders = await getOrdersWithFulfillment();

  const paid = orders.filter((o) => o.financial_status === "paid");
  const shipped = orders.filter((o) => o.fulfillment?.status === "shipped");
  const pendingFulfillment = paid.filter(
    (o) => o.fulfillment?.status !== "shipped"
  );
  const revenue = paid.reduce((s, o) => s + parseFloat(o.total_price || "0"), 0);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-zinc-100">Orders</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Live order status and CJ fulfillment tracking
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <StatCard label="Total Orders" value={orders.length} />
        <StatCard label="Paid" value={paid.length} />
        <StatCard
          label="Pending Fulfillment"
          value={pendingFulfillment.length}
          highlight={pendingFulfillment.length > 0}
        />
        <StatCard label="Shipped" value={shipped.length} />
        <StatCard label="Revenue" value={`$${revenue.toFixed(2)}`} />
      </div>

      <OrdersTable orders={orders} />
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
