"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { RelayProvider } from "@/lib/relay-context";
import { DashboardNav } from "@/components/DashboardNav";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { Footer } from "@/components/Footer";
import { MobilePremiumGate } from "@/components/MobilePremiumGate";

const DASHBOARD_PREFIXES = [
  "/connect",
  "/live",
  "/tickers",
  "/settings",
  "/lists",
  "/history",
  "/calendar",
];

/** Pages that require premium access on mobile (i.e. all board pages except /connect). */
const GATED_PREFIXES = ["/live", "/tickers", "/settings", "/lists", "/history", "/calendar"];

export function ClientLayout({
  children,
  nav,
}: {
  children: React.ReactNode;
  nav: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const isDashboard = DASHBOARD_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
  const isGated = GATED_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));

  return (
    <RelayProvider>
      {isDashboard ? (
        <>
          <DashboardNav />
          <DisclaimerBanner />
          <main className="p-6 pb-20 sm:pb-6">
            {isGated ? <MobilePremiumGate>{children}</MobilePremiumGate> : children}
          </main>
        </>
      ) : (
        <>
          {nav}
          <main className="flex-1">{children}</main>
          <Footer />
        </>
      )}
    </RelayProvider>
  );
}
