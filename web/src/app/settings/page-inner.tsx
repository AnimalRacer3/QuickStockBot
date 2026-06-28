"use client";

import { useEffect, useState } from "react";
import { useRelay } from "@/lib/relay-context";
import { RiskSizingControl } from "@/components/settings/RiskSizingControl";
import type { BotSettings, DailyTargetMode } from "@/lib/types";

const ALL_PATTERNS = [
  "bullish_engulfing",
  "hammer",
  "morning_star",
  "bullish_continuation",
  "doji",
  "piercing_line",
];

export const DEFAULT_SETTINGS: BotSettings = {
  bot_id: "",
  pre_open_lead_hours: 1.0,
  scan_duration_hours: 3.0,
  scanner_refresh_seconds: 60,
  relative_volume_min: 2.0,
  gap_up_min_pct: 5.0,
  max_float_shares: 20_000_000,
  include_unknown_float: true,
  require_news: true,
  active_tickers_n: 5,
  prior_profit_bias_weight: 0.5,
  enabled_patterns: ["bullish_engulfing", "hammer", "morning_star", "bullish_continuation"],
  pattern_candle_lookback: 5,
  macd_fast: 12,
  macd_slow: 26,
  macd_signal: 9,
  macd_slope_lookback: 3,
  macd_enforce_above_zero: false,
  risk_per_trade_pct: 1.0,
  daily_max_loss_pct: 10.0,
  daily_profit_target_pct: 7.0,
  override_risk_per_trade: false,
  flatten_on_daily_loss: true,
  flatten_on_daily_profit: false,
  daily_target_mode: "giveback",
  daily_giveback_pct: 25.0,
  exit_mode: "trail_off",
  trail_off_trigger: "candle_pattern",
  trail_off_fraction_per_candle: 0.25,
  stop_loss_pct: 2.0,
  take_profit_pct: 4.0,
  trailing_stop_enabled: false,
  force_close_at_close: true,
};

export default function SettingsPageInner() {
  const { client } = useRelay();
  const [settings, setSettings] = useState<BotSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");
  const [riskError, setRiskError] = useState("");

  useEffect(() => {
    if (!client) return;
    setLoading(true);
    client
      .getSettings()
      .then((s) => {
        setSettings({ ...DEFAULT_SETTINGS, ...s });
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [client]);

  function set<K extends keyof BotSettings>(key: K, value: BotSettings[K]) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  function handleRiskChange(value: number) {
    setRiskError("");
    if (settings.override_risk_per_trade && value >= settings.daily_profit_target_pct) {
      setRiskError(`Must be less than daily target (${settings.daily_profit_target_pct}%)`);
    }
    set("risk_per_trade_pct", value);
  }

  function handleOverrideChange(enabled: boolean) {
    setRiskError("");
    set("override_risk_per_trade", enabled);
    if (!enabled) {
      const computed = parseFloat((settings.daily_profit_target_pct / 5).toFixed(1));
      set("risk_per_trade_pct", computed);
    }
  }

  function togglePattern(p: string) {
    const current = settings.enabled_patterns;
    if (current.includes(p)) {
      set(
        "enabled_patterns",
        current.filter((x) => x !== p)
      );
    } else {
      set("enabled_patterns", [...current, p]);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (riskError) return;
    if (!client) return;
    setSaving(true);
    try {
      const updated = await client.updateSettings(settings);
      setSettings({ ...DEFAULT_SETTINGS, ...updated });
      setSavedMsg("Settings saved.");
      setTimeout(() => setSavedMsg(""), 3000);
    } catch (err) {
      setSavedMsg(`Error: ${err instanceof Error ? err.message : "Save failed"}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={{ color: "#9ca3af" }}>Loading settings…</div>;

  return (
    <form
      onSubmit={handleSave}
      style={{ display: "flex", flexDirection: "column", gap: 32, maxWidth: 720 }}
    >
      {/* Scanner */}
      <section>
        <h2 style={sectionTitleStyle}>Scanner</h2>
        <div style={gridStyle}>
          <Field label="Pre-Open Lead (hours)">
            <input
              type="number"
              step="0.5"
              value={settings.pre_open_lead_hours}
              onChange={(e) => set("pre_open_lead_hours", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Scan Duration (hours)">
            <input
              type="number"
              step="0.5"
              value={settings.scan_duration_hours}
              onChange={(e) => set("scan_duration_hours", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Refresh Interval (sec)">
            <input
              type="number"
              step="1"
              value={settings.scanner_refresh_seconds}
              onChange={(e) => set("scanner_refresh_seconds", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Min RVOL">
            <input
              type="number"
              step="0.1"
              value={settings.relative_volume_min}
              onChange={(e) => set("relative_volume_min", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Gap Up Min (%)">
            <input
              type="number"
              step="0.5"
              value={settings.gap_up_min_pct}
              onChange={(e) => set("gap_up_min_pct", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Max Float Shares">
            <input
              type="number"
              step="1000000"
              value={settings.max_float_shares}
              onChange={(e) => set("max_float_shares", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Active Tickers (N)">
            <input
              type="number"
              step="1"
              min="1"
              value={settings.active_tickers_n}
              onChange={(e) => set("active_tickers_n", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Prior Profit Bias Weight">
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={settings.prior_profit_bias_weight}
              onChange={(e) => set("prior_profit_bias_weight", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
        </div>
        <div style={{ display: "flex", gap: 24, marginTop: 12 }}>
          <ToggleField
            label="Include Unknown Float"
            checked={settings.include_unknown_float}
            onChange={(v) => set("include_unknown_float", v)}
          />
          <ToggleField
            label="Require News"
            checked={settings.require_news}
            onChange={(v) => set("require_news", v)}
          />
        </div>
      </section>

      {/* Patterns / MACD */}
      <section>
        <h2 style={sectionTitleStyle}>Patterns / MACD</h2>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 8 }}>Enabled Patterns</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {ALL_PATTERNS.map((p) => (
              <label
                key={p}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                  fontSize: 13,
                  color: "#d1d5db",
                }}
              >
                <input
                  type="checkbox"
                  checked={settings.enabled_patterns.includes(p)}
                  onChange={() => togglePattern(p)}
                />
                {p}
              </label>
            ))}
          </div>
        </div>
        <div style={gridStyle}>
          <Field label="Pattern Candle Lookback">
            <input
              type="number"
              step="1"
              value={settings.pattern_candle_lookback}
              onChange={(e) => set("pattern_candle_lookback", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="MACD Fast">
            <input
              type="number"
              step="1"
              value={settings.macd_fast}
              onChange={(e) => set("macd_fast", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="MACD Slow">
            <input
              type="number"
              step="1"
              value={settings.macd_slow}
              onChange={(e) => set("macd_slow", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="MACD Signal">
            <input
              type="number"
              step="1"
              value={settings.macd_signal}
              onChange={(e) => set("macd_signal", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="MACD Slope Lookback">
            <input
              type="number"
              step="1"
              value={settings.macd_slope_lookback}
              onChange={(e) => set("macd_slope_lookback", parseInt(e.target.value))}
              style={inputStyle}
            />
          </Field>
        </div>
        <div style={{ marginTop: 12 }}>
          <ToggleField
            label="Enforce MACD Above Zero"
            checked={settings.macd_enforce_above_zero}
            onChange={(v) => set("macd_enforce_above_zero", v)}
          />
        </div>
      </section>

      {/* Risk & Daily Limits */}
      <section>
        <h2 style={sectionTitleStyle}>Risk & Daily Limits</h2>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 8 }}>Daily Target Mode</div>
          <div style={{ display: "flex", gap: 12 }}>
            {(["stop", "giveback"] as const).map((mode) => (
              <label
                key={mode}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                  fontSize: 13,
                  color: "#d1d5db",
                }}
              >
                <input
                  type="radio"
                  name="daily_target_mode"
                  value={mode}
                  checked={settings.daily_target_mode === mode}
                  onChange={() => set("daily_target_mode", mode as DailyTargetMode)}
                />
                {mode === "stop" ? "Stop (hard stop at target)" : "Giveback (trail from peak)"}
              </label>
            ))}
          </div>
        </div>
        <div style={gridStyle}>
          <Field label="Daily Max Loss (%)">
            <input
              type="number"
              step="0.5"
              value={settings.daily_max_loss_pct}
              onChange={(e) => set("daily_max_loss_pct", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field
            label={
              settings.daily_target_mode === "giveback"
                ? "Giveback Activation Threshold (%)"
                : "Daily Profit Target (%)"
            }
          >
            <input
              type="number"
              step="0.5"
              value={settings.daily_profit_target_pct}
              onChange={(e) => set("daily_profit_target_pct", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          {settings.daily_target_mode === "giveback" && (
            <Field label="Giveback % from Peak">
              <input
                type="number"
                step="1"
                min="1"
                max="100"
                value={settings.daily_giveback_pct}
                onChange={(e) => set("daily_giveback_pct", parseFloat(e.target.value))}
                style={inputStyle}
              />
            </Field>
          )}
        </div>
        <div style={{ display: "flex", gap: 24, margin: "12px 0" }}>
          <ToggleField
            label="Flatten on Daily Loss"
            checked={settings.flatten_on_daily_loss}
            onChange={(v) => set("flatten_on_daily_loss", v)}
          />
          {settings.daily_target_mode === "stop" && (
            <ToggleField
              label="Flatten on Daily Profit"
              checked={settings.flatten_on_daily_profit}
              onChange={(v) => set("flatten_on_daily_profit", v)}
            />
          )}
        </div>
        <div style={{ maxWidth: 360 }}>
          <RiskSizingControl
            dailyPct={settings.daily_profit_target_pct}
            riskPct={settings.risk_per_trade_pct}
            overrideEnabled={settings.override_risk_per_trade}
            onOverrideChange={handleOverrideChange}
            onRiskChange={handleRiskChange}
            riskError={riskError}
          />
        </div>
      </section>

      {/* Exits */}
      <section>
        <h2 style={sectionTitleStyle}>Exits</h2>
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, color: "#d1d5db", display: "block", marginBottom: 6 }}>
            Exit Mode
          </label>
          <div style={{ display: "flex", gap: 12 }}>
            {(["dump", "trail_off"] as const).map((mode) => (
              <label
                key={mode}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                  fontSize: 13,
                  color: "#d1d5db",
                }}
              >
                <input
                  type="radio"
                  name="exit_mode"
                  value={mode}
                  checked={settings.exit_mode === mode}
                  onChange={() => set("exit_mode", mode)}
                />
                {mode === "dump" ? "Dump (immediate)" : "Trail Off"}
              </label>
            ))}
          </div>
        </div>
        {settings.exit_mode === "trail_off" && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 8 }}>Trail Off Trigger</div>
            <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
              {(["per_candle", "candle_pattern"] as const).map((mode) => (
                <label
                  key={mode}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    cursor: "pointer",
                    fontSize: 13,
                    color: "#d1d5db",
                  }}
                >
                  <input
                    type="radio"
                    name="trail_off_trigger"
                    value={mode}
                    checked={(settings.trail_off_trigger ?? "candle_pattern") === mode}
                    onChange={() => set("trail_off_trigger", mode)}
                  />
                  {mode === "per_candle"
                    ? "Per Candle (sell fraction every candle)"
                    : "Candle Pattern (sell on pattern change)"}
                </label>
              ))}
            </div>
            <div style={gridStyle}>
              <Field label="Fraction Per Candle">
                <input
                  type="number"
                  step="0.05"
                  min="0.05"
                  max="1"
                  value={settings.trail_off_fraction_per_candle ?? 0.25}
                  onChange={(e) => set("trail_off_fraction_per_candle", parseFloat(e.target.value))}
                  style={inputStyle}
                />
              </Field>
            </div>
          </div>
        )}
        <div style={gridStyle}>
          <Field label="Stop Loss (%)">
            <input
              type="number"
              step="0.1"
              value={settings.stop_loss_pct}
              onChange={(e) => set("stop_loss_pct", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          <Field label="Take Profit (%)">
            <input
              type="number"
              step="0.1"
              value={settings.take_profit_pct}
              onChange={(e) => set("take_profit_pct", parseFloat(e.target.value))}
              style={inputStyle}
            />
          </Field>
          {settings.trailing_stop_enabled && (
            <Field label="Trailing Stop (%)">
              <input
                type="number"
                step="0.1"
                value={settings.trailing_stop_pct ?? ""}
                onChange={(e) => set("trailing_stop_pct", parseFloat(e.target.value))}
                style={inputStyle}
              />
            </Field>
          )}
        </div>
        <div style={{ display: "flex", gap: 24, marginTop: 12 }}>
          <ToggleField
            label="Trailing Stop"
            checked={settings.trailing_stop_enabled}
            onChange={(v) => set("trailing_stop_enabled", v)}
          />
          <ToggleField
            label="Force Close at Close"
            checked={settings.force_close_at_close}
            onChange={(v) => set("force_close_at_close", v)}
          />
        </div>
      </section>

      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <button
          type="submit"
          disabled={saving || !!riskError}
          style={{
            padding: "10px 24px",
            borderRadius: 8,
            border: "none",
            backgroundColor: "#3b82f6",
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            opacity: saving || riskError ? 0.6 : 1,
            cursor: saving || riskError ? "not-allowed" : "pointer",
          }}
        >
          {saving ? "Saving…" : "Save Settings"}
        </button>
        {savedMsg && (
          <span
            style={{ fontSize: 13, color: savedMsg.startsWith("Error") ? "#ef4444" : "#34d399" }}
          >
            {savedMsg}
          </span>
        )}
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label
      style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "#d1d5db" }}
    >
      {label}
      {children}
    </label>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        cursor: "pointer",
        fontSize: 13,
        color: "#9ca3af",
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ width: 14, height: 14 }}
      />
      {label}
    </label>
  );
}

const sectionTitleStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 700,
  color: "#9ca3af",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  marginBottom: 16,
  paddingBottom: 8,
  borderBottom: "1px solid #1f2937",
};

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
  gap: 16,
};

const inputStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 6,
  border: "1px solid #374151",
  backgroundColor: "#1f2937",
  color: "#f9fafb",
  fontSize: 14,
  outline: "none",
};
