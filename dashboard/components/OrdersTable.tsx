"use client";

import type { ShopifyOrder } from "@/lib/shopify";
import type { Fulfillment } from "@/lib/supabase";

type MergedOrder = ShopifyOrder & { fulfillment: Fulfillment | null };

const STATUS_MAP: Record<
  string,
  { label: string; dot: string; text: string }
> = {
  pending: { label: "Pending CJ", dot: "bg-amber-500", text: "text-amber-400" },
  cj_placed: { label: "CJ Placed", dot: "bg-indigo-500", text: "text-indigo-400" },
  shipped: { label: "Shipped", dot: "bg-emerald-500", text: "text-emerald-400" },
  error: { label: "Error", dot: "bg-rose-500", text: "text-rose-400" },
};

function FulfillmentStatus({ order }: { order: MergedOrder }) {
  if (!order.fulfillment) {
    if (order.financial_status === "paid") {
      return (
        <span className="flex items-center gap-1.5 text-amber-400 text-xs">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
          Awaiting CJ
        </span>
      );
    }
    return <span className="text-zinc-600 text-xs">—</span>;
  }
  const s = STATUS_MAP[order.fulfillment.status] || STATUS_MAP.pending;
  return (
    <span className={`flex items-center gap-1.5 text-xs ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

export default function OrdersTable({ orders }: { orders: MergedOrder[] }) {
  if (orders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-zinc-600">
        <div className="text-4xl mb-3">◻</div>
        <p className="text-sm">No orders yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/50">
            {["Order", "Date", "Customer", "Items", "Total", "CJ Order", "Status", "Tracking"].map(
              (h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wide"
                >
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60">
          {orders.map((o) => {
            const customer =
              o.customer
                ? `${o.customer.first_name} ${o.customer.last_name}`
                : o.shipping_address?.name || "—";
            const items = o.line_items
              .map((li) => `${li.title} ×${li.quantity}`)
              .join(", ");
            const tracking = o.fulfillment?.tracking_number;
            const cjId = o.fulfillment?.cj_order_id;

            return (
              <tr
                key={o.id}
                className="bg-zinc-900 hover:bg-zinc-800/50 transition-colors"
              >
                <td className="px-4 py-3 font-mono text-zinc-100 text-xs">
                  {o.name}
                </td>
                <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">
                  {new Date(o.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-zinc-300 max-w-[140px] truncate">
                  {customer}
                </td>
                <td className="px-4 py-3 text-zinc-400 max-w-[200px] truncate text-xs">
                  {items}
                </td>
                <td className="px-4 py-3 text-zinc-100 font-medium tabular-nums">
                  ${parseFloat(o.total_price).toFixed(2)}
                </td>
                <td className="px-4 py-3 font-mono text-zinc-500 text-xs">
                  {cjId || "—"}
                </td>
                <td className="px-4 py-3">
                  <FulfillmentStatus order={o} />
                </td>
                <td className="px-4 py-3 font-mono text-indigo-400 text-xs">
                  {tracking ? (
                    <span title={o.fulfillment?.carrier || ""}>{tracking}</span>
                  ) : (
                    <span className="text-zinc-600">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
