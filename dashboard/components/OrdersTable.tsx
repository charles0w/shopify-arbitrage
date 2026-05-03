"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { ShopifyOrder } from "@/lib/shopify";
import type { Fulfillment } from "@/lib/supabase";

type MergedOrder = ShopifyOrder & { fulfillment: Fulfillment | null };

function RetryButton({ orderId }: { orderId: string }) {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);

  async function retry() {
    setState("loading");
    setErr(null);
    try {
      const resp = await fetch(`/api/orders/${orderId}/retry`, { method: "POST" });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error(j.error || `HTTP ${resp.status}`);
      }
      router.refresh();
    } catch (e) {
      setState("error");
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  if (state === "error") {
    return (
      <span className="text-xs text-rose-400" title={err || ""}>
        retry failed
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={retry}
      disabled={state === "loading"}
      className="text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-50"
    >
      {state === "loading" ? "…" : "Retry"}
    </button>
  );
}

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
  // Surface error_message on any non-shipped status. PR #5 covered status='error'
  // (CJ placement failed); 'cj_placed' with error_message means CJ is shipped
  // but tracking push to Shopify is failing — different bug, equally hidden.
  const errMsg = order.fulfillment.error_message || "";
  const showErr = errMsg && order.fulfillment.status !== "shipped";
  return (
    <span
      className={`flex items-center gap-1.5 text-xs ${s.text}`}
      title={showErr ? errMsg : undefined}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
      {showErr && (
        <span className="text-zinc-500 truncate max-w-[160px]">— {errMsg}</span>
      )}
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
            {["Order", "Date", "Customer", "Items", "Total", "CJ Order", "Status", "Tracking", ""].map(
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
                <td className="px-4 py-3 text-right">
                  {o.fulfillment?.status === "error" && (
                    <RetryButton orderId={String(o.id)} />
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
