import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import React from "react";
import type { BotSettings } from "@/lib/types";

// Minimal mock of the relay client
const mockSettings: BotSettings = {
  bot_id: "test-bot",
  pre_open_lead_hours: 1.0,
  scan_duration_hours: 3.0,
  scanner_refresh_seconds: 60,
  relative_volume_min: 2.0,
  gap_up_min_pct: 5.0,
  max_float_shares: 20_000_000,
  include_unknown_float: true,
  require_news: true,
  active_tickers_n: 3,
  prior_profit_bias_weight: 0.5,
  enabled_patterns: ["bullish_engulfing", "hammer"],
  pattern_candle_lookback: 5,
  macd_fast: 12,
  macd_slow: 26,
  macd_signal: 9,
  macd_slope_lookback: 3,
  macd_enforce_above_zero: true,
  risk_per_trade_pct: 1.0,
  daily_max_loss_pct: 3.0,
  daily_profit_target_pct: 5.0,
  override_risk_per_trade: false,
  flatten_on_daily_loss: true,
  flatten_on_daily_profit: false,
  daily_target_mode: "giveback",
  daily_giveback_pct: 25.0,
  exit_mode: "dump",
  stop_loss_pct: 2.0,
  take_profit_pct: 4.0,
  trailing_stop_enabled: false,
  force_close_at_close: true,
};

// We test the SettingsPage by injecting a mock RelayContext
// Since SettingsPage reads from context, we provide a mock context value
import { RelayContext } from "@/lib/relay-context-testable";
import SettingsPageInner from "@/app/settings/page-inner";

describe("Settings round-trip", () => {
  function buildMockClient(savedSettings = { ...mockSettings }) {
    return {
      getSettings: vi.fn().mockResolvedValue({ ...savedSettings }),
      updateSettings: vi.fn().mockImplementation(async (patch: Partial<BotSettings>) => {
        Object.assign(savedSettings, patch);
        return { ...savedSettings };
      }),
    };
  }

  function renderWithClient(client: ReturnType<typeof buildMockClient>) {
    return render(
      <RelayContext.Provider
        value={{
          client: client as unknown as import("@/lib/relay-client").RelayClient,
          connectionState: "connected",
          connect: vi.fn(),
          disconnect: vi.fn(),
          tickers: [],
          logs: [],
        }}
      >
        <SettingsPageInner />
      </RelayContext.Provider>
    );
  }

  it("loads settings from relay on mount", async () => {
    const client = buildMockClient();
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalledOnce());
  });

  it("pre_open_lead_hours field has correct initial value", async () => {
    const client = buildMockClient();
    renderWithClient(client);
    await waitFor(() => {
      const inputs = screen.getAllByDisplayValue("1");
      expect(inputs.length).toBeGreaterThan(0);
    });
  });

  it("calls updateSettings with patch on save", async () => {
    const client = buildMockClient();
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    const saveBtn = screen.getByText("Save Settings");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(client.updateSettings).toHaveBeenCalledOnce();
      const patch = client.updateSettings.mock.calls[0][0] as BotSettings;
      expect(patch.enabled_patterns).toContain("bullish_engulfing");
      expect(patch.exit_mode).toBe("dump");
      expect(patch.macd_fast).toBe(12);
      expect(patch.daily_profit_target_pct).toBe(5.0);
    });
  });

  it("trail_off fields appear when exit_mode set to trail_off", async () => {
    const client = buildMockClient();
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    const trailRadio = screen.getByDisplayValue("trail_off");
    fireEvent.click(trailRadio);

    expect(screen.getByText("Trail Off Trigger (%)")).toBeDefined();
  });

  it("trail_off fields hidden when exit_mode=dump", async () => {
    const client = buildMockClient();
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    expect(screen.queryByText("Trail Off Trigger (%)")).toBeNull();
  });

  it("include_unknown_float toggle persisted in patch", async () => {
    const client = buildMockClient();
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    // Find and toggle include_unknown_float checkbox
    const checkboxes = screen.getAllByRole<HTMLInputElement>("checkbox");
    // The label text is "Include Unknown Float" - find it by iterating
    const ufCheckbox = checkboxes.find((cb) => {
      const parent = cb.parentElement;
      return parent?.textContent?.includes("Include Unknown Float");
    });
    expect(ufCheckbox).toBeDefined();
    // It's currently true, toggle it off
    fireEvent.click(ufCheckbox!);

    fireEvent.click(screen.getByText("Save Settings"));
    await waitFor(() => {
      expect(client.updateSettings).toHaveBeenCalled();
      const patch = client.updateSettings.mock.calls[0][0] as BotSettings;
      expect(patch.include_unknown_float).toBe(false);
    });
  });

  // Section 18: giveback mode UI tests
  it("giveback mode shows daily_giveback_pct field", async () => {
    const client = buildMockClient({ ...mockSettings, daily_target_mode: "giveback" });
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    expect(screen.getByText("Giveback % from Peak")).toBeDefined();
  });

  it("giveback mode shows activation threshold label instead of profit target", async () => {
    const client = buildMockClient({ ...mockSettings, daily_target_mode: "giveback" });
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    expect(screen.getByText("Giveback Activation Threshold (%)")).toBeDefined();
    expect(screen.queryByText("Daily Profit Target (%)")).toBeNull();
  });

  it("stop mode hides giveback_pct field and shows flatten_on_daily_profit", async () => {
    const client = buildMockClient({ ...mockSettings, daily_target_mode: "stop" });
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    expect(screen.queryByText("Giveback % from Peak")).toBeNull();
    expect(screen.getByText("Flatten on Daily Profit")).toBeDefined();
  });

  it("switching to giveback mode hides flatten_on_daily_profit toggle", async () => {
    // Start in stop mode, then switch to giveback
    const client = buildMockClient({ ...mockSettings, daily_target_mode: "stop" });
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    // Switch to giveback
    const givebackRadio = screen.getByDisplayValue("giveback");
    fireEvent.click(givebackRadio);

    expect(screen.queryByText("Flatten on Daily Profit")).toBeNull();
    expect(screen.getByText("Giveback % from Peak")).toBeDefined();
  });

  it("switching to giveback and saving includes daily_target_mode and daily_giveback_pct", async () => {
    const client = buildMockClient({ ...mockSettings, daily_target_mode: "stop" });
    renderWithClient(client);
    await waitFor(() => expect(client.getSettings).toHaveBeenCalled());

    const givebackRadio = screen.getByDisplayValue("giveback");
    fireEvent.click(givebackRadio);

    fireEvent.click(screen.getByText("Save Settings"));
    await waitFor(() => {
      expect(client.updateSettings).toHaveBeenCalled();
      const patch = client.updateSettings.mock.calls[0][0] as BotSettings;
      expect(patch.daily_target_mode).toBe("giveback");
      expect(patch.daily_giveback_pct).toBe(25.0);
    });
  });
});
