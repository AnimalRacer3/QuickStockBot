"use client";

import { useEffect, useState } from "react";

interface Props {
  dailyPct: number; // daily_profit_target_pct
  riskPct: number; // risk_per_trade_pct (current / override value)
  overrideEnabled: boolean;
  onOverrideChange: (enabled: boolean) => void;
  onRiskChange: (value: number) => void;
  riskError?: string;
}

export function RiskSizingControl({
  dailyPct,
  riskPct,
  overrideEnabled,
  onOverrideChange,
  onRiskChange,
  riskError,
}: Props) {
  const [inputValue, setInputValue] = useState(String(riskPct));

  useEffect(() => {
    setInputValue(String(riskPct));
  }, [riskPct]);

  const goalTrades = dailyPct > 0 && riskPct > 0 ? Math.ceil(dailyPct / riskPct) : "—";

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setInputValue(e.target.value);
    const n = parseFloat(e.target.value);
    if (!isNaN(n)) onRiskChange(n);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 13, color: "#d1d5db", display: "block", marginBottom: 4 }}>
            Risk Per Trade (%)
          </label>
          <div style={{ position: "relative" }}>
            <input
              type="number"
              step="0.1"
              min="0.1"
              aria-label="Risk per trade percent"
              disabled={!overrideEnabled}
              value={overrideEnabled ? inputValue : riskPct.toFixed(1)}
              onChange={handleInputChange}
              style={{
                ...inputStyle,
                color: overrideEnabled ? "#f9fafb" : "#6b7280",
                backgroundColor: overrideEnabled ? "#1f2937" : "#111827",
                cursor: overrideEnabled ? "text" : "not-allowed",
                borderColor: riskError ? "#ef4444" : overrideEnabled ? "#374151" : "#1f2937",
              }}
            />
            {!overrideEnabled && (
              <span
                style={{
                  position: "absolute",
                  right: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  fontSize: 10,
                  color: "#4b5563",
                  pointerEvents: "none",
                }}
              >
                DAILY÷{Math.ceil(dailyPct / (riskPct || 1))}
              </span>
            )}
          </div>
          {riskError && (
            <div role="alert" style={{ color: "#ef4444", fontSize: 12, marginTop: 4 }}>
              {riskError}
            </div>
          )}
        </div>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "#9ca3af" }}>
        <input
          type="checkbox"
          checked={overrideEnabled}
          onChange={(e) => onOverrideChange(e.target.checked)}
          aria-label="Override risk per trade"
          style={{ width: 14, height: 14, cursor: "pointer" }}
        />
        Override risk per trade
      </label>

      <div
        aria-live="polite"
        style={{ fontSize: 12, color: "#6b7280", backgroundColor: "#111827", borderRadius: 6, padding: "6px 10px" }}
      >
        Goal: reach daily target in ~<strong style={{ color: "#f9fafb" }}>{goalTrades}</strong> trades
        {typeof goalTrades === "number" && (
          <span style={{ marginLeft: 6 }}>
            ({dailyPct.toFixed(1)}% ÷ {riskPct.toFixed(1)}%)
          </span>
        )}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: 6,
  border: "1px solid #374151",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
};
