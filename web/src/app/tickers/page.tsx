"use client";

import { useRelay } from "@/lib/relay-context";
import { TickerTable } from "@/components/TickerTable";

export default function TickersPage() {
  const { tickers, connectionState } = useRelay();

  if (connectionState !== "connected") {
    return (
      <div style={{ color: "#9ca3af", textAlign: "center", marginTop: 80 }}>
        Not connected. <a href="/connect" style={{ color: "#3b82f6" }}>Connect first</a>.
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Active Tickers</h1>
      <TickerTable tickers={tickers} />
    </div>
  );
}
