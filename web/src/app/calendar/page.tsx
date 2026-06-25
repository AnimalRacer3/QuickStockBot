"use client";

import { useEffect, useState } from "react";
import { useRelay } from "@/lib/relay-context";
import { CalendarGrid } from "@/components/CalendarGrid";
import type { DailyPL, TradeDetail } from "@/lib/types";

export default function CalendarPage() {
  const { client, connectionState } = useRelay();
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1); // 1-12
  const [days, setDays] = useState<DailyPL[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDay, setSelectedDay] = useState<DailyPL | null>(null);
  const [dayTrades, setDayTrades] = useState<TradeDetail[]>([]);
  const [loadingTrades, setLoadingTrades] = useState(false);

  useEffect(() => {
    if (connectionState !== "connected" || !client) return;
    setLoading(true);
    client
      .getDailyPL(year, month)
      .then(({ days: d }) => {
        setDays(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [client, connectionState, year, month]);

  useEffect(() => {
    if (!selectedDay || !client) return;
    setLoadingTrades(true);
    client
      .getTradeHistory(100, 0)
      .then(({ trades }) => {
        const filtered = trades.filter((t) => t.timestamp.startsWith(selectedDay.date));
        setDayTrades(filtered);
        setLoadingTrades(false);
      })
      .catch(() => setLoadingTrades(false));
  }, [selectedDay, client]);

  function prevMonth() {
    if (month === 1) {
      setYear((y) => y - 1);
      setMonth(12);
    } else setMonth((m) => m - 1);
    setSelectedDay(null);
  }

  function nextMonth() {
    if (month === 12) {
      setYear((y) => y + 1);
      setMonth(1);
    } else setMonth((m) => m + 1);
    setSelectedDay(null);
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
    <div style={{ maxWidth: 640 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20 }}>Calendar</h1>
      {loading ? (
        <div style={{ color: "#9ca3af" }}>Loading…</div>
      ) : (
        <CalendarGrid
          year={year}
          month={month}
          days={days}
          onDayClick={(day) => setSelectedDay(day)}
          onPrevMonth={prevMonth}
          onNextMonth={nextMonth}
        />
      )}

      {selectedDay && (
        <div style={{ marginTop: 28 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>
              {selectedDay.date} — {selectedDay.total_pl >= 0 ? "+" : ""}
              {selectedDay.total_pl.toFixed(2)} ({selectedDay.trade_count} trades)
            </h2>
            <button
              onClick={() => setSelectedDay(null)}
              style={{
                background: "none",
                border: "none",
                color: "#4b5563",
                cursor: "pointer",
                fontSize: 18,
              }}
            >
              ×
            </button>
          </div>
          {loadingTrades ? (
            <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading trades…</div>
          ) : dayTrades.length === 0 ? (
            <div style={{ color: "#4b5563", fontSize: 13 }}>No trades found for this day.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr>
                  {["Symbol", "Type", "Time", "Qty", "Price", "P&L"].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: "left",
                        padding: "8px 12px",
                        color: "#6b7280",
                        fontSize: 11,
                        textTransform: "uppercase",
                        borderBottom: "1px solid #1f2937",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dayTrades.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid #1a2332" }}>
                    <td style={{ padding: "8px 12px", color: "#60a5fa", fontWeight: 600 }}>
                      {t.symbol}
                    </td>
                    <td style={{ padding: "8px 12px", color: "#e5e7eb" }}>{t.type}</td>
                    <td style={{ padding: "8px 12px", color: "#9ca3af" }}>
                      {t.timestamp.slice(11, 19)}
                    </td>
                    <td style={{ padding: "8px 12px", color: "#e5e7eb" }}>{t.qty}</td>
                    <td style={{ padding: "8px 12px", color: "#e5e7eb" }}>${t.price.toFixed(2)}</td>
                    <td
                      style={{ padding: "8px 12px", color: t.net_pl >= 0 ? "#34d399" : "#f87171" }}
                    >
                      {t.net_pl >= 0 ? "+" : ""}
                      {t.net_pl.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
