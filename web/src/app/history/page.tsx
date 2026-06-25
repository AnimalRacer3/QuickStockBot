"use client";

import { useEffect, useState } from "react";
import { useRelay } from "@/lib/relay-context";
import type { TradeDetail } from "@/lib/types";

type FilterType = "all" | "buy" | "sell" | "short";
type FilterStatus = "all" | "filled" | "partial" | "cancelled" | "rejected";

export default function HistoryPage() {
  const { client, connectionState } = useRelay();
  const [trades, setTrades] = useState<TradeDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [filterTicker, setFilterTicker] = useState("");
  const [selected, setSelected] = useState<TradeDetail | null>(null);

  const LIMIT = 50;

  useEffect(() => {
    if (connectionState !== "connected" || !client) return;
    setLoading(true);
    client
      .getTradeHistory(LIMIT, offset)
      .then(({ trades: t, total: tot }) => {
        setTrades(t);
        setTotal(tot);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [client, connectionState, offset]);

  const filtered = trades.filter((t) => {
    if (filterType !== "all" && t.type !== filterType) return false;
    if (filterStatus !== "all" && t.status !== filterStatus) return false;
    if (filterTicker && !t.symbol.includes(filterTicker.toUpperCase())) return false;
    return true;
  });

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

  if (selected) {
    return <TradeDetailView trade={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Trade History</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as FilterType)}
          style={selectStyle}
        >
          <option value="all">All Types</option>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
          <option value="short">Short</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
          style={selectStyle}
        >
          <option value="all">All Statuses</option>
          <option value="filled">Filled</option>
          <option value="partial">Partial</option>
          <option value="cancelled">Cancelled</option>
          <option value="rejected">Rejected</option>
        </select>
        <input
          type="text"
          placeholder="Filter by ticker…"
          value={filterTicker}
          onChange={(e) => setFilterTicker(e.target.value)}
          style={{ ...selectStyle, width: 160 }}
        />
      </div>

      {loading ? (
        <div style={{ color: "#9ca3af" }}>Loading…</div>
      ) : (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                {["Type", "Timestamp", "Symbol", "Qty", "Price", "P&L", "Status"].map((h) => (
                  <th key={h} style={thStyle}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr
                  key={t.id}
                  onClick={() => setSelected(t)}
                  style={{ cursor: "pointer", borderBottom: "1px solid #1a2332" }}
                >
                  <td style={tdStyle}>{t.type}</td>
                  <td style={tdStyle}>{t.timestamp}</td>
                  <td style={{ ...tdStyle, fontWeight: 600, color: "#60a5fa" }}>{t.symbol}</td>
                  <td style={tdStyle}>{t.qty}</td>
                  <td style={tdStyle}>${t.price.toFixed(2)}</td>
                  <td style={{ ...tdStyle, color: t.net_pl >= 0 ? "#34d399" : "#f87171" }}>
                    {t.net_pl >= 0 ? "+" : ""}
                    {t.net_pl.toFixed(2)}
                  </td>
                  <td style={tdStyle}>{t.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div style={{ textAlign: "center", color: "#4b5563", padding: 32 }}>
              No trades match filters
            </div>
          )}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: 16,
              fontSize: 13,
              color: "#6b7280",
            }}
          >
            <span>
              Showing {filtered.length} of {total} trades
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                disabled={offset === 0}
                style={pageBtnStyle}
              >
                Previous
              </button>
              <button
                onClick={() => setOffset(offset + LIMIT)}
                disabled={offset + LIMIT >= total}
                style={pageBtnStyle}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function TradeDetailView({ trade, onBack }: { trade: TradeDetail; onBack: () => void }) {
  return (
    <div style={{ maxWidth: 600 }}>
      <button
        onClick={onBack}
        style={{
          background: "none",
          border: "none",
          color: "#6b7280",
          cursor: "pointer",
          fontSize: 13,
          marginBottom: 16,
          padding: 0,
        }}
      >
        ← Back to Trade History
      </button>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20 }}>
        Trade Detail — {trade.symbol}
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        {[
          ["Symbol", trade.symbol],
          ["P&L", `${trade.net_pl >= 0 ? "+" : ""}${trade.net_pl.toFixed(2)}`],
          ["Status", trade.status],
          ["Label", trade.label],
          ["Opened", trade.opened_at ?? "—"],
          ["Closed", trade.closed_at ?? "—"],
        ].map(([k, v]) => (
          <div
            key={k}
            style={{
              backgroundColor: "#111827",
              borderRadius: 6,
              padding: "10px 14px",
              border: "1px solid #1f2937",
            }}
          >
            <div
              style={{
                color: "#6b7280",
                fontSize: 11,
                textTransform: "uppercase",
                marginBottom: 4,
              }}
            >
              {k}
            </div>
            <div style={{ fontSize: 14 }}>{v}</div>
          </div>
        ))}
      </div>
      <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: "#9ca3af" }}>
        Status History
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {(trade.status_history ?? []).map((h, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 16,
              fontSize: 13,
              padding: "6px 10px",
              backgroundColor: "#111827",
              borderRadius: 4,
            }}
          >
            <span style={{ color: "#4b5563" }}>{h.timestamp}</span>
            <span style={{ color: "#e5e7eb" }}>{h.status}</span>
            {h.filled_price && (
              <span style={{ color: "#60a5fa" }}>@ ${h.filled_price.toFixed(2)}</span>
            )}
          </div>
        ))}
        {(!trade.status_history || trade.status_history.length === 0) && (
          <div style={{ color: "#4b5563", fontSize: 13 }}>No status history</div>
        )}
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 14px",
  color: "#6b7280",
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  borderBottom: "1px solid #1f2937",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 14px",
  color: "#e5e7eb",
  whiteSpace: "nowrap",
};

const selectStyle: React.CSSProperties = {
  padding: "6px 10px",
  borderRadius: 6,
  border: "1px solid #374151",
  backgroundColor: "#1f2937",
  color: "#e5e7eb",
  fontSize: 13,
};

const pageBtnStyle: React.CSSProperties = {
  padding: "4px 12px",
  borderRadius: 4,
  border: "1px solid #374151",
  backgroundColor: "#1f2937",
  color: "#9ca3af",
  cursor: "pointer",
  fontSize: 12,
};
