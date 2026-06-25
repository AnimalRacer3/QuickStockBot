"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { RelayProvider } from "@/lib/relay-context";
import { Nav } from "@/components/Nav";
import { DashboardNav } from "@/components/DashboardNav";
import { Footer } from "@/components/Footer";

const DASHBOARD_PREFIXES = [
  "/connect",
  "/live",
  "/tickers",
  "/settings",
  "/lists",
  "/history",
  "/calendar",
];

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const isDashboard = DASHBOARD_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );

  return (
    <RelayProvider>
      {isDashboard ? (
        <>
          <DashboardNav />
          <main style={{ padding: "24px" }}>{children}</main>
        </>
      ) : (
        <>
          <Nav />
          <main className="flex-1">{children}</main>
          <Footer />
        </>
      )}
    </RelayProvider>
  );
}
