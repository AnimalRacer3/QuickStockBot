export interface Setting {
  key: string;
  value: string;
  updatedAt: number;
}

export const DEFAULT_SETTINGS: Record<string, string> = {
  max_position_size: '1000',
  max_open_positions: '5',
  stop_loss_pct: '0.05',
  take_profit_pct: '0.10',
  rsi_oversold: '30',
  rsi_overbought: '70',
  ema_short_period: '9',
  ema_long_period: '21',
  scan_interval_ms: '60000',
  min_volume: '100000',
  paper_trading: 'true',
  // Section 4 — technical analysis
  macd_fast: '12',
  macd_slow: '26',
  macd_signal: '9',
  macd_slope_lookback: '3',
  macd_enforce_above_zero: 'true',
  pattern_candle_lookback: '5',
  enabled_patterns: 'bullish_engulfing,hammer,morning_star,bullish_continuation',
};
