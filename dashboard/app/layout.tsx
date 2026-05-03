import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Arbitrage Dashboard",
  description: "Shopify dropshipping arbitrage — product queue & order tracking",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex h-screen overflow-hidden bg-zinc-950">
        <Sidebar />
        <main className="flex-1 overflow-y-auto pt-12 md:pt-0">
          {children}
        </main>
      </body>
    </html>
  );
}
