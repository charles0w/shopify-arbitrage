"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/queue", label: "Queue", icon: "⬡" },
  { href: "/orders", label: "Orders", icon: "◈" },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-56 shrink-0 h-screen sticky top-0 flex flex-col bg-zinc-900 border-r border-zinc-800">
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
  );
}
