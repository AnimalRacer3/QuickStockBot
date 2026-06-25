"use client";

import type { DailyPL } from "@/lib/types";

function dayColor(day: DailyPL): string {
  if (day.trade_count === 0) return "blue";
  if (day.total_pl > 0) return "green";
  if (day.total_pl < 0) return "red";
  return "blue"; // ran but flat
}

function dayBg(color: string): string {
  switch (color) {
    case "green":
      return "#14532d";
    case "red":
      return "#450a0a";
    case "blue":
      return "#1e3a5f";
    default:
      return "transparent";
  }
}

function dayBorder(color: string): string {
  switch (color) {
    case "green":
      return "#166534";
    case "red":
      return "#7f1d1d";
    case "blue":
      return "#1e40af";
    default:
      return "transparent";
  }
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function firstWeekday(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay();
}

function fmtDay(pl: number): string {
  if (pl === 0) return "Flat";
  const sign = pl > 0 ? "+" : "";
  if (Math.abs(pl) >= 1000) return `${sign}${(pl / 1000).toFixed(1)}K`;
  return `${sign}${pl.toFixed(0)}`;
}

interface Props {
  year: number;
  month: number; // 1-12
  days: DailyPL[];
  onDayClick?: (day: DailyPL) => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export function CalendarGrid({ year, month, days, onDayClick, onPrevMonth, onNextMonth }: Props) {
  const dayMap = new Map(days.map((d) => [d.date, d]));
  const totalDays = daysInMonth(year, month);
  const startOffset = firstWeekday(year, month);
  const cells: Array<number | null> = [
    ...Array(startOffset).fill(null),
    ...Array.from({ length: totalDays }, (_, i) => i + 1),
  ];

  // Pad to full weeks
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
        <button onClick={onPrevMonth} aria-label="Previous month" style={navBtnStyle}>
          ‹
        </button>
        <span style={{ fontSize: 18, fontWeight: 700, minWidth: 180, textAlign: "center" }}>
          {MONTHS[month - 1]} {year}
        </span>
        <button onClick={onNextMonth} aria-label="Next month" style={navBtnStyle}>
          ›
        </button>
      </div>

      {/* Weekday labels */}
      <div
        style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginBottom: 4 }}
      >
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            style={{
              textAlign: "center",
              fontSize: 11,
              color: "#4b5563",
              fontWeight: 700,
              padding: "4px 0",
            }}
          >
            {d}
          </div>
        ))}
      </div>

      {/* Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4 }}>
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} style={{ height: 64, borderRadius: 6 }} />;
          }
          const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const pl = dayMap.get(dateStr);
          const color = pl ? dayColor(pl) : null;

          return (
            <div
              key={day}
              onClick={() => pl && onDayClick?.(pl)}
              data-testid={`calendar-day-${dateStr}`}
              data-color={color ?? ""}
              style={{
                height: 64,
                borderRadius: 6,
                border: `1px solid ${color ? dayBorder(color) : "#1f2937"}`,
                backgroundColor: color ? dayBg(color) : "#111827",
                cursor: pl ? "pointer" : "default",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                transition: "opacity 0.1s",
              }}
            >
              <span
                style={{
                  fontSize: 13,
                  fontWeight: pl ? 600 : 400,
                  color: pl ? "#f9fafb" : "#374151",
                }}
              >
                {day}
              </span>
              {pl && (
                <span
                  data-testid={`calendar-pl-${dateStr}`}
                  style={{
                    fontSize: 11,
                    color: color === "green" ? "#4ade80" : color === "red" ? "#f87171" : "#93c5fd",
                    fontWeight: 600,
                  }}
                >
                  {fmtDay(pl.total_pl)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 20, marginTop: 16, fontSize: 12, color: "#6b7280" }}>
        {[
          { color: "green", label: "Profit" },
          { color: "red", label: "Loss" },
          { color: "blue", label: "Ran / Flat" },
        ].map(({ color, label }) => (
          <div key={color} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: 3,
                backgroundColor: dayBg(color),
                border: `1px solid ${dayBorder(color)}`,
              }}
            />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

const navBtnStyle: React.CSSProperties = {
  padding: "4px 12px",
  borderRadius: 6,
  border: "1px solid #374151",
  backgroundColor: "#1f2937",
  color: "#e5e7eb",
  cursor: "pointer",
  fontSize: 18,
  lineHeight: 1,
};
