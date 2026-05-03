"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const nav = [
  { href: "/stats", label: "Overview", icon: "◇" },
  { href: "/queue", label: "Queue", icon: "⬡" },
  { href: "/orders", label: "Orders", icon: "◈" },
];

export default function Sidebar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [path]);

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-30 h-12 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center text-white text-[10px] font-bold">
            A
          </div>
          <span className="text-sm font-semibold text-zinc-100">Arbitrage</span>
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close menu" : "Open menu"}
          className="text-zinc-300 hover:text-zinc-100 text-xl leading-none w-8 h-8 flex items-center justify-center"
        >
          {open ? "✕" : "☰"}
        </button>
      </div>

      {/* Backdrop (mobile only, when open) */}
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
          className="md:hidden fixed inset-0 z-30 bg-black/50"
        />
      )}

      <aside
        className={`fixed md:sticky top-0 left-0 z-40 w-56 shrink-0 h-screen flex-col bg-zinc-900 border-r border-zinc-800 transition-transform duration-200 ${
          open ? "translate-x-0 flex" : "-translate-x-full md:translate-x-0 hidden md:flex"
        }`}
      >
        {/* Brand */}
        <div className="px-5 py-5 border-b border-zinc-800">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">
              A
            </div>
            <div>
              <div className="text-sm font-semibold text-zinc-100">Arbitrage</div>
              <div className="text-[10px] text-zinc-500 leading-none mt-0.5">charles-arbitrage-store</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {nav.map(({ href, label, icon }) => {
            const active = path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-zinc-800 text-zinc-100 font-medium"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                }`}
              >
                <span className="text-base leading-none opacity-70">{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-zinc-800">
          <a
            href={`https://charles-arbitrage-store.myshopify.com/admin`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Open Shopify Admin ↗
          </a>
        </div>
      </aside>
    </>
  );
}
