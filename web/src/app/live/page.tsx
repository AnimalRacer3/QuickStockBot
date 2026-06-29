"use client";

import { useState } from "react";
import { useRelay } from "@/lib/relay-context";

const CATEGORY_COLORS: Record<string, string> = {
  info: "#60a5fa",
  warning: "#fbbf24",
  error: "#f87171",
  trade: "#34d399",
  order: "#a78bfa",
  system: "#9ca3af",
};

export default function LivePage() {
  const { logs, connectionState, client } = useRelay();
  const [scanStatus, setScanStatus] = useState("");

  async function handleTriggerScan() {
    if (!client) return;
    setScanStatus("Queuing scan…");
    try {
      await client.triggerScan();
      setScanStatus("Scan queued — results appear in the Tickers page within seconds.");
      setTimeout(() => setScanStatus(""), 6000);
    } catch (err) {
      setScanStatus(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    }
  }

  if (connectionState !== "connected") {
    return (
      <div style={{ color: "#9ca3af", textAlign: "center", marginTop: 80 }}>
        Not connected.{" "}
        <a href="/connect" style={{ color: "#3b82f6" }}>
          Connect first
        </a>
        .
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Live Actions</h1>
        <button
          onClick={handleTriggerScan}
          style={{
            padding: "8px 18px",
            borderRadius: 8,
            border: "none",
            backgroundColor: "#10b981",
            color: "#fff",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Trigger Scan
        </button>
        {scanStatus && (
          <span
            style={{
              fontSize: 13,
              color: scanStatus.startsWith("Error") ? "#ef4444" : "#34d399",
            }}
          >
            {scanStatus}
          </span>
        )}
      </div>
      <div
        role="log"
        aria-live="polite"
        style={{
          backgroundColor: "#111827",
          borderRadius: 8,
          border: "1px solid #1f2937",
          padding: 16,
          fontFamily: "monospace",
          fontSize: 12,
          maxHeight: "70vh",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        {logs.length === 0 && <span style={{ color: "#4b5563" }}>Waiting for log events…</span>}
        {logs.map((log, i) => (
          <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
            <span style={{ color: "#4b5563", whiteSpace: "nowrap" }}>
              {log.timestamp.replace("T", " ").replace("Z", "")}
            </span>
            <span
              style={{
                color: CATEGORY_COLORS[log.category] ?? "#9ca3af",
                minWidth: 56,
                textTransform: "uppercase",
                fontSize: 10,
                fontWeight: 700,
                paddingTop: 1,
              }}
            >
              {log.category}
            </span>
            <span style={{ color: "#e5e7eb" }}>{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
