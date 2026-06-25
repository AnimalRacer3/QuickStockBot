import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TickerTable } from "./TickerTable";
import type { ExtendedTickerState } from "@/lib/types";

const BASE: ExtendedTickerState = {
  symbol: "AAPL",
  last_price: 15.5,
  high_of_day: 16.0,
  low_of_day: 14.8,
  macd_line: 0.12,
  macd_signal_line: 0.08,
  macd_hist: 0.04,
  pattern_tags: [],
  score: 72,
  updated_at: "2024-03-05T10:00:00Z",
  unknown_float: false,
  tradable: true,
  rvol: 3.2,
  pct_change: 4.5,
  float_shares: 8_500_000,
  role: "leader",
};

const UNKNOWN: ExtendedTickerState = {
  ...BASE,
  symbol: "XYZ",
  unknown_float: true,
  tradable: false,
  float_shares: undefined,
};

describe("TickerTable", () => {
  it("renders ticker symbol", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.getByText("AAPL")).toBeDefined();
  });

  it("does NOT show unknown-float badge for known float", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.queryByTestId("unknown-float-badge")).toBeNull();
  });

  it("shows unknown-float badge when unknown_float=true", () => {
    render(<TickerTable tickers={[UNKNOWN]} />);
    const badge = screen.getByTestId("unknown-float-badge");
    expect(badge).toBeDefined();
    expect(badge.textContent).toBe("UNKNOWN");
  });

  it("shows UNKNOWN badge even when ticker is not tradable", () => {
    render(<TickerTable tickers={[UNKNOWN]} />);
    expect(screen.getByTestId("unknown-float-badge")).toBeDefined();
    expect(screen.getByText("No")).toBeDefined();
  });

  it("renders RVOL with × suffix", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.getByText("3.2×")).toBeDefined();
  });

  it("renders % change with + sign for positive", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.getByText("+4.50%")).toBeDefined();
  });

  it("shows float in millions", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.getByText("8.5M")).toBeDefined();
  });

  it("shows role", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.getByText("leader")).toBeDefined();
  });

  it("shows tradable=Yes for tradable ticker", () => {
    render(<TickerTable tickers={[BASE]} />);
    expect(screen.getByText("Yes")).toBeDefined();
  });

  it("shows tradable=No for non-tradable ticker", () => {
    render(<TickerTable tickers={[UNKNOWN]} />);
    expect(screen.getByText("No")).toBeDefined();
  });

  it("renders empty state when no tickers", () => {
    render(<TickerTable tickers={[]} />);
    expect(screen.getByText("No active tickers")).toBeDefined();
  });

  it("renders multiple tickers", () => {
    render(<TickerTable tickers={[BASE, UNKNOWN]} />);
    expect(screen.getByText("AAPL")).toBeDefined();
    expect(screen.getByText("XYZ")).toBeDefined();
  });

  it("shows multiple unknown-float badges when multiple unknown tickers", () => {
    const second: ExtendedTickerState = { ...UNKNOWN, symbol: "FOO" };
    render(<TickerTable tickers={[UNKNOWN, second]} />);
    const badges = screen.getAllByTestId("unknown-float-badge");
    expect(badges.length).toBe(2);
  });
});
