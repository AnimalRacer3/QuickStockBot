"use client";

import Link from "next/link";
import type { ExtendedTickerState } from "@/lib/types";

function macdFavorability(t: ExtendedTickerState): string {
  if (t.macd_hist > 0 && t.macd_line > 0) return "Strong";
  if (t.macd_hist > 0) return "Positive";
  if (t.macd_hist < 0 && t.macd_line < 0) return "Weak";
  return "Negative";
}

function fmt(n: number | undefined, decimals = 2): string {
  if (n === undefined || n === null) return "—";
  return n.toFixed(decimals);
}

function fmtFloat(n: number | undefined): string {
  if (n === undefined || n === null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return n.toString();
}

interface Props {
  tickers: ExtendedTickerState[];
}

export function TickerTable({ tickers }: Props) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Symbol</th>
            <th style={thStyle}>Price</th>
            <th style={thStyle}>% Change</th>
            <th style={thStyle}>RVOL</th>
            <th style={thStyle}>Float</th>
            <th style={thStyle}>Unknown Float</th>
            <th style={thStyle}>MACD</th>
            <th style={thStyle}>Role</th>
            <th style={thStyle}>Score</th>
            <th style={thStyle}>Tradable</th>
          </tr>
        </thead>
        <tbody>
          {tickers.map((t) => (
            <tr
              key={t.symbol}
              style={{
                ...rowStyle,
                opacity: t.tradable ? 1 : 0.6,
              }}
            >
              <td style={tdStyle}>
                <Link href={`/tickers/${t.symbol}`} style={{ color: "#60a5fa", textDecoration: "none", fontWeight: 600 }}>
                  {t.symbol}
                </Link>
              </td>
              <td style={tdStyle}>${fmt(t.last_price)}</td>
              <td style={{ ...tdStyle, color: (t.pct_change ?? 0) >= 0 ? "#34d399" : "#f87171" }}>
                {t.pct_change !== undefined ? `${t.pct_change >= 0 ? "+" : ""}${fmt(t.pct_change)}%` : "—"}
              </td>
              <td style={tdStyle}>{fmt(t.rvol, 1)}×</td>
              <td style={tdStyle}>{fmtFloat(t.float_shares)}</td>
              <td style={{ ...tdStyle, textAlign: "center" }}>
                {t.unknown_float ? (
                  <span
                    data-testid="unknown-float-badge"
                    style={{
                      display: "inline-block",
                      padding: "2px 8px",
                      borderRadius: 4,
                      backgroundColor: "#78350f",
                      color: "#fbbf24",
                      fontSize: 11,
                      fontWeight: 700,
                      border: "1px solid #92400e",
                    }}
                  >
                    UNKNOWN
                  </span>
                ) : (
                  <span style={{ color: "#4b5563" }}>—</span>
                )}
              </td>
              <td style={tdStyle}>{macdFavorability(t)}</td>
              <td style={tdStyle}>{t.role ?? "—"}</td>
              <td style={tdStyle}>{fmt(t.score, 0)}</td>
              <td style={{ ...tdStyle, textAlign: "center" }}>
                {t.tradable ? (
                  <span style={{ color: "#34d399", fontWeight: 600 }}>Yes</span>
                ) : (
                  <span style={{ color: "#6b7280" }}>No</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {tickers.length === 0 && (
        <div style={{ textAlign: "center", color: "#4b5563", padding: 32 }}>No active tickers</div>
      )}
    </div>
  );
}

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 14px",
  color: "#6b7280",
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  borderBottom: "1px solid #1f2937",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 14px",
  borderBottom: "1px solid #1a2332",
  color: "#e5e7eb",
  whiteSpace: "nowrap",
};

const rowStyle: React.CSSProperties = {
  transition: "background 0.1s",
};
