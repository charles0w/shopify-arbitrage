"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { QueueItem } from "@/lib/supabase";
import Image from "next/image";
import DOMPurify from "isomorphic-dompurify";

type Status = QueueItem["status"];

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 70 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-400 w-7 text-right">{pct}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const map: Record<Status, { label: string; cls: string }> = {
    pending: { label: "Pending", cls: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
    approved: { label: "Approved", cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
    rejected: { label: "Rejected", cls: "bg-zinc-700 text-zinc-400 border-zinc-600" },
  };
  const { label, cls } = map[status];
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${cls}`}>
      {label}
    </span>
  );
}

function Card({
  item: init,
  selected,
  onToggleSelect,
}: {
  item: QueueItem;
  selected: boolean;
  onToggleSelect: (id: string) => void;
}) {
  const [item, setItem] = useState(init);
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const safeBody = useMemo(
    () =>
      item.listing_body_html
        ? DOMPurify.sanitize(item.listing_body_html, { USE_PROFILES: { html: true } })
        : "",
    [item.listing_body_html]
  );

  async function act(action: "approve" | "reject") {
    setLoading(action);
    setErr(null);
    try {
      const resp = await fetch(`/api/queue/${item.id}/${action}`, { method: "POST" });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.error || "Unknown error");
      setItem((p) => ({ ...p, status: action === "approve" ? "approved" : "rejected" }));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  const isPending = item.status === "pending";
  const displayTitle = item.listing_title || item.title;

  return (
    <div className={`bg-zinc-900 border rounded-xl overflow-hidden transition-opacity ${
      item.status === "rejected" ? "opacity-40" : "border-zinc-800"
    }`}>
      {/* Image */}
      <div className="relative w-full h-44 bg-zinc-800">
        {item.image_url ? (
          <Image
            src={item.image_url}
            alt={displayTitle}
            fill
            className="object-contain p-3"
            unoptimized
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-600 text-2xl">
            ◻
          </div>
        )}
        {isPending && (
          <label className="absolute top-2 left-2 inline-flex items-center justify-center w-6 h-6 rounded bg-zinc-900/80 backdrop-blur cursor-pointer hover:bg-zinc-800/90">
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(item.id)}
              className="w-4 h-4 accent-indigo-500 cursor-pointer"
              aria-label={`Select ${displayTitle}`}
            />
          </label>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Title + status */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-zinc-100 leading-snug line-clamp-2">
            {displayTitle}
          </p>
          <StatusBadge status={item.status} />
        </div>

        {/* Niche */}
        <span className="inline-block text-[11px] px-2 py-0.5 rounded-full bg-indigo-600/15 text-indigo-400 border border-indigo-600/20 font-medium">
          {item.keyword}
        </span>

        {/* Score */}
        <div>
          <div className="flex justify-between text-[11px] text-zinc-500 mb-1">
            <span>Score</span>
          </div>
          <ScoreBar score={item.score} />
        </div>

        {/* Pricing */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-zinc-400">${item.supplier_price_usd.toFixed(2)} cost</span>
          <span className="text-zinc-100 font-semibold">
            ${item.suggested_sale_price_usd.toFixed(2)} sale
          </span>
        </div>

        {/* Listing preview toggle */}
        {item.listing_body_html && (
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            {showPreview ? "▾ Hide preview" : "▸ Preview listing"}
          </button>
        )}
        {showPreview && safeBody && (
          <div className="bg-zinc-950/60 border border-zinc-800 rounded-lg p-3 max-h-64 overflow-y-auto text-xs text-zinc-300 listing-preview">
            <div dangerouslySetInnerHTML={{ __html: safeBody }} />
          </div>
        )}

        {/* Error */}
        {err && (
          <p className="text-xs text-rose-400 bg-rose-500/10 rounded px-2 py-1">{err}</p>
        )}

        {/* Actions */}
        {isPending && (
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => act("approve")}
              disabled={loading !== null}
              className="flex-1 py-2 rounded-lg text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50"
            >
              {loading === "approve" ? "…" : "Approve"}
            </button>
            <button
              onClick={() => act("reject")}
              disabled={loading !== null}
              className="flex-1 py-2 rounded-lg text-sm font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-50"
            >
              {loading === "reject" ? "…" : "Reject"}
            </button>
          </div>
        )}

        {item.status === "approved" && item.shopify_product_id && (
          <a
            href={`https://charles-arbitrage-store.myshopify.com/admin/products/${item.shopify_product_id}`}
            target="_blank"
            rel="noreferrer"
            className="block text-center text-xs text-indigo-400 hover:text-indigo-300 pt-1"
          >
            View in Shopify ↗
          </a>
        )}
      </div>
    </div>
  );
}

function SelectionBar({
  selectedIds,
  pendingIds,
  onSelectAll,
  onClear,
}: {
  selectedIds: string[];
  pendingIds: string[];
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (selectedIds.length === 0) {
    return (
      <div className="flex items-center gap-3 mb-5">
        <p className="text-sm text-zinc-500">
          {pendingIds.length} pending in queue
        </p>
        {pendingIds.length > 0 && (
          <button
            type="button"
            onClick={onSelectAll}
            className="text-xs text-indigo-400 hover:text-indigo-300"
          >
            Select all pending
          </button>
        )}
      </div>
    );
  }

  async function approveSelected() {
    setBusy(true);
    setErr(null);
    setProgress(`Approving ${selectedIds.length}…`);
    try {
      const resp = await fetch("/api/queue/bulk/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: selectedIds }),
      });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.error || `HTTP ${resp.status}`);
      const failed = json.failed ?? 0;
      const approved = json.approved ?? 0;
      if (failed > 0) {
        const firstErr = (json.results || []).find(
          (r: { ok: boolean }) => !r.ok
        );
        setErr(
          `${approved} approved, ${failed} failed${
            firstErr?.error ? `: ${firstErr.error}` : ""
          }`
        );
      }
      onClear();
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  async function rejectSelected() {
    setBusy(true);
    setErr(null);
    setProgress(`Rejecting ${selectedIds.length}…`);
    try {
      const resp = await fetch("/api/queue/bulk/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: selectedIds }),
      });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.error || `HTTP ${resp.status}`);
      onClear();
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 bg-indigo-500/10 border border-indigo-500/30 rounded-lg px-4 py-2.5">
      <p className="text-sm text-indigo-300 font-medium">
        {selectedIds.length} selected
      </p>
      <div className="flex-1" />
      {progress && (
        <p className="text-xs text-zinc-400">{progress}</p>
      )}
      {err && (
        <p className="text-xs text-rose-400 max-w-md truncate" title={err}>
          {err}
        </p>
      )}
      <button
        type="button"
        onClick={onClear}
        disabled={busy}
        className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 disabled:opacity-50"
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={rejectSelected}
        disabled={busy}
        className="px-3 py-1.5 rounded-md text-sm font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-50"
      >
        {busy ? "…" : `Reject ${selectedIds.length}`}
      </button>
      <button
        type="button"
        onClick={approveSelected}
        disabled={busy}
        className="px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50"
      >
        {busy ? "…" : `Approve ${selectedIds.length}`}
      </button>
    </div>
  );
}

export default function QueueGrid({ items }: { items: QueueItem[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const pendingIds = useMemo(
    () => items.filter((i) => i.status === "pending").map((i) => i.id),
    [items]
  );

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-zinc-600">
        <div className="text-4xl mb-3">◻</div>
        <p className="text-sm">No products in queue for this date.</p>
        <p className="text-xs mt-1 text-zinc-700">Run <code className="font-mono">python -m pipeline.daily_research</code> to populate.</p>
      </div>
    );
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const approved = items.filter((i) => i.status === "approved").length;
  const rejected = items.filter((i) => i.status === "rejected").length;
  const selectedIds = Array.from(selected).filter((id) => pendingIds.includes(id));

  return (
    <div>
      <SelectionBar
        selectedIds={selectedIds}
        pendingIds={pendingIds}
        onSelectAll={() => setSelected(new Set(pendingIds))}
        onClear={() => setSelected(new Set())}
      />
      <p className="text-xs text-zinc-600 mb-4 -mt-2">
        {pendingIds.length} pending · {approved} approved · {rejected} rejected
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {items.map((item) => (
          <Card
            key={item.id}
            item={item}
            selected={selected.has(item.id)}
            onToggleSelect={toggle}
          />
        ))}
      </div>
    </div>
  );
}
