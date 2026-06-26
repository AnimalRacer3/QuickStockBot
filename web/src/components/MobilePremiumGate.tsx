"use client";

import React, { useEffect, useState } from "react";
import type { Tier } from "@/lib/plan";

/** Returns true when the viewport is narrower than Tailwind's sm breakpoint (640 px). */
function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return isMobile;
}

/** Fetches the current user's tier from the server. */
function useUserTier(): { tier: Tier; loading: boolean } {
  const [tier, setTier] = useState<Tier>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/user/tier")
      .then((r) => r.json())
      .then((data: { tier: Tier }) => setTier(data.tier))
      .catch(() => setTier(null))
      .finally(() => setLoading(false));
  }, []);

  return { tier, loading };
}

/**
 * Wraps board pages (not /connect) with a premium-on-mobile gate.
 * Desktop: always renders children.
 * Mobile + premium/trialing: renders children.
 * Mobile + basic (non-premium): renders the upgrade notice.
 */
export function MobilePremiumGate({ children }: { children: React.ReactNode }) {
  const isMobile = useIsMobile();
  const { tier, loading } = useUserTier();

  // On desktop, or while loading, pass through immediately (avoids flash on desktop).
  if (!isMobile || loading) return <>{children}</>;

  // Mobile + premium access: pass through.
  if (tier === "premium") return <>{children}</>;

  // Mobile + basic (or unknown): show the gate.
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        textAlign: "center",
        padding: "32px 24px",
      }}
    >
      <div
        style={{
          backgroundColor: "#111827",
          border: "1px solid #1f2937",
          borderRadius: 12,
          padding: "32px 28px",
          maxWidth: 360,
          width: "100%",
        }}
      >
        <div style={{ fontSize: 36, marginBottom: 12 }}>📱</div>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#f9fafb", marginBottom: 8 }}>
          Premium required on mobile
        </h2>
        <p style={{ color: "#9ca3af", fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
          Board pages are available on mobile with a Premium plan. Upgrade to access live data,
          tickers, settings, history, and more on your phone.
        </p>
        <a
          href="/billing"
          style={{
            display: "inline-block",
            padding: "10px 24px",
            backgroundColor: "#3b82f6",
            color: "#fff",
            borderRadius: 8,
            fontWeight: 600,
            fontSize: 14,
            textDecoration: "none",
          }}
        >
          Upgrade to Premium
        </a>
      </div>
    </div>
  );
}
