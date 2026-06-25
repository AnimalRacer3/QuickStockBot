"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRelay } from "@/lib/relay-context";
import type { ExtendedTickerState } from "@/lib/types";

function PriceRangeChart({ ticker }: { ticker: ExtendedTickerState }) {
  const { low_of_day, high_of_day, last_price } = ticker;
  const range = high_of_day - low_of_day || 1;
  const currentPct = Math.min(1, Math.max(0, (last_price - low_of_day) / range));

  return (
    <svg
      width="280"
      height="80"
      aria-label={`Price range: low ${low_of_day}, high ${high_of_day}, current ${last_price}`}
      style={{ overflow: "visible" }}
    >
      {/* Range bar */}
      <rect x={20} y={30} width={240} height={20} rx={4} fill="#1f2937" />
      {/* Current price marker */}
      <rect x={20 + currentPct * 240 - 2} y={20} width={4} height={40} rx={2} fill="#60a5fa" />
      {/* Low label */}
      <text x={20} y={68} fill="#6b7280" fontSize={11}>
        ${low_of_day.toFixed(2)}
      </text>
      {/* High label */}
      <text x={260} y={68} textAnchor="end" fill="#6b7280" fontSize={11}>
        ${high_of_day.toFixed(2)}
      </text>
      {/* Current label */}
      <text
        x={20 + currentPct * 240}
        y={14}
        textAnchor="middle"
        fill="#f9fafb"
        fontSize={12}
        fontWeight="bold"
      >
        ${last_price.toFixed(2)}
      </text>
    </svg>
  );
}

function macdFavorability(t: ExtendedTickerState): string {
  if (t.macd_hist > 0 && t.macd_line > 0) return "Strong bullish";
  if (t.macd_hist > 0) return "Bullish";
  if (t.macd_hist < 0 && t.macd_line < 0) return "Strong bearish";
  return "Bearish";
}

function fmtFloat(n: number | undefined): string {
  if (n === undefined) return "Unknown";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return n.toString();
}

export default function TickerDetailPage({ params }: { params: { symbol: string } }) {
  const { client, connectionState, tickers } = useRelay();
  const [ticker, setTicker] = useState<ExtendedTickerState | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (connectionState !== "connected" || !client) return;
    const fromContext = tickers.find((t) => t.symbol === params.symbol);
    if (fromContext) {
      setTicker(fromContext);
      return;
    }
    client
      .getTickerDetail(params.symbol)
      .then(setTicker)
      .catch((e: Error) => setError(e.message));
  }, [client, connectionState, params.symbol, tickers]);

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

  if (error) return <div style={{ color: "#ef4444" }}>Error: {error}</div>;
  if (!ticker) return <div style={{ color: "#9ca3af" }}>Loading…</div>;

  return (
    <div style={{ maxWidth: 640 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Link href="/tickers" style={{ color: "#6b7280", textDecoration: "none", fontSize: 13 }}>
          ← Active Tickers
        </Link>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>{ticker.symbol}</h1>
        {ticker.unknown_float && (
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 4,
              backgroundColor: "#78350f",
              color: "#fbbf24",
              fontSize: 11,
              fontWeight: 700,
              border: "1px solid #92400e",
            }}
          >
            UNKNOWN FLOAT
          </span>
        )}
        {!ticker.tradable && (
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 4,
              backgroundColor: "#1f2937",
              color: "#6b7280",
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            NOT TRADABLE
          </span>
        )}
      </div>

      <div style={{ marginBottom: 28 }}>
        <PriceRangeChart ticker={ticker} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {[
          ["Last Price", `$${ticker.last_price.toFixed(2)}`],
          ["High of Day", `$${ticker.high_of_day.toFixed(2)}`],
          ["Low of Day", `$${ticker.low_of_day.toFixed(2)}`],
          [
            "% Change",
            ticker.pct_change !== undefined
              ? `${ticker.pct_change >= 0 ? "+" : ""}${ticker.pct_change.toFixed(2)}%`
              : "—",
          ],
          ["RVOL", ticker.rvol !== undefined ? `${ticker.rvol.toFixed(1)}×` : "—"],
          ["Float", fmtFloat(ticker.float_shares)],
          ["MACD Hist", ticker.macd_hist.toFixed(4)],
          ["MACD Favorability", macdFavorability(ticker)],
          ["Role", ticker.role ?? "—"],
          ["Score", ticker.score.toFixed(0)],
        ].map(([label, value]) => (
          <div
            key={label}
            style={{
              backgroundColor: "#111827",
              borderRadius: 8,
              padding: "12px 16px",
              border: "1px solid #1f2937",
            }}
          >
            <div
              style={{
                color: "#6b7280",
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 4,
              }}
            >
              {label}
            </div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>{value}</div>
          </div>
        ))}
      </div>

      {ticker.pattern_tags.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div
            style={{
              color: "#6b7280",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 8,
            }}
          >
            Patterns
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {ticker.pattern_tags.map((p) => (
              <span
                key={p}
                style={{
                  padding: "4px 10px",
                  borderRadius: 4,
                  backgroundColor: "#1e3a5f",
                  color: "#93c5fd",
                  fontSize: 12,
                  border: "1px solid #1e40af",
                }}
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
