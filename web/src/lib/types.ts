// Extended types for the web dashboard.
// The shared/types/index.ts contract is frozen; web-local extensions live here.

export interface ExtendedTickerState {
  symbol: string;
  last_price: number;
  high_of_day: number;
  low_of_day: number;
  macd_line: number;
  macd_signal_line: number;
  macd_hist: number;
  pattern_tags: string[];
  score: number;
  updated_at: string;
  // Scanner fields added in Section 5
  rvol?: number;
  pct_change?: number;
  float_shares?: number;
  unknown_float: boolean;
  tradable: boolean;
  role?: "leader" | "laggard" | null;
  gap_pct?: number;
}

export type ExitMode = "dump" | "trail_off";
export type DailyTargetMode = "stop" | "giveback";

export interface BotSettings {
  // Identity
  bot_id: string;
  relay_url?: string;
  paper_trading?: boolean;
  auto_trade?: boolean;
  max_positions?: number;
  min_score?: number;

  // Scanner
  pre_open_lead_hours: number;
  scan_duration_hours: number;
  scanner_refresh_seconds: number;
  relative_volume_min: number;
  gap_up_min_pct: number;
  max_float_shares: number;
  include_unknown_float: boolean;
  require_news: boolean;
  active_tickers_n: number;
  prior_profit_bias_weight: number;

  // MACD / Patterns
  enabled_patterns: string[];
  pattern_candle_lookback: number;
  macd_fast: number;
  macd_slow: number;
  macd_signal: number;
  macd_slope_lookback: number;
  macd_enforce_above_zero: boolean;

  // Risk & daily limits
  risk_per_trade_pct: number;
  daily_max_loss_pct: number;
  daily_profit_target_pct: number;
  override_risk_per_trade: boolean;
  flatten_on_daily_loss: boolean;
  flatten_on_daily_profit: boolean;
  daily_target_mode: DailyTargetMode;
  daily_giveback_pct: number;

  // Exits
  exit_mode: ExitMode;
  trail_off_trigger?: number;
  trail_off_fraction_per_candle?: number;
  trail_off_pattern?: string;
  stop_loss_pct: number;
  take_profit_pct: number;
  trailing_stop_enabled: boolean;
  trailing_stop_pct?: number;
  force_close_at_close: boolean;
}

export interface DailyPL {
  date: string; // YYYY-MM-DD
  total_pl: number;
  trade_count: number;
}

export interface TradeRow {
  id: string;
  symbol: string;
  type: string;
  timestamp: string;
  qty: number;
  price: number;
  net_pl: number;
  status: string;
}

export interface OrderStatusHistory {
  status: string;
  timestamp: string;
  filled_qty?: number;
  filled_price?: number;
}

export interface TradeDetail extends TradeRow {
  entry_order: {
    id: string;
    type: string;
    qty: number;
    submitted_price: number;
    filled_price?: number;
    status: string;
    submitted_at?: string;
  };
  exit_order: {
    id: string;
    type: string;
    qty: number;
    submitted_price: number;
    filled_price?: number;
    status: string;
    submitted_at?: string;
  };
  status_history: OrderStatusHistory[];
  opened_at?: string;
  closed_at?: string;
  label: string;
}
