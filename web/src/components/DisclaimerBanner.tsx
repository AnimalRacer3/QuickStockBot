"use client";

import { useState } from "react";

export function DisclaimerBanner() {
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return sessionStorage.getItem("disclaimer-dismissed") === "1";
  });

  if (dismissed) return null;

  function dismiss() {
    sessionStorage.setItem("disclaimer-dismissed", "1");
    setDismissed(true);
  }

  return (
    <div
      role="note"
      aria-label="Disclaimer"
      style={{
        backgroundColor: "#1c1f26",
        borderBottom: "1px solid #2d3748",
        padding: "8px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        fontSize: 12,
        color: "#9ca3af",
      }}
    >
      <span>
        <strong style={{ color: "#f59e0b" }}>Not financial advice.</strong> QuickStockBot automates
        order submission based on technical signals. It does not provide investment advice. Past
        performance does not guarantee future results.{" "}
        <span style={{ color: "#6b7280" }}>
          Margin/PDT: post-June 4 2026 rules apply — $2 k margin minimum, intraday-margin-based
          buying power; bot defers to Alpaca.
        </span>
      </span>
      <button
        onClick={dismiss}
        aria-label="Dismiss disclaimer"
        style={{
          background: "none",
          border: "none",
          color: "#4b5563",
          cursor: "pointer",
          fontSize: 16,
          lineHeight: 1,
          padding: "0 4px",
          flexShrink: 0,
        }}
      >
        ×
      </button>
    </div>
  );
}
