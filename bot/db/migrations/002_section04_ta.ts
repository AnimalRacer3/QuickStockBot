export const migration002 = {
  version: 2,
  name: '002_section04_ta',
  sql: `
    INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
      ('macd_fast',               '12',                                                          strftime('%s', 'now')),
      ('macd_slow',               '26',                                                          strftime('%s', 'now')),
      ('macd_signal',             '9',                                                           strftime('%s', 'now')),
      ('macd_slope_lookback',     '3',                                                           strftime('%s', 'now')),
      ('macd_enforce_above_zero', 'true',                                                        strftime('%s', 'now')),
      ('pattern_candle_lookback', '5',                                                           strftime('%s', 'now')),
      ('enabled_patterns',        'bullish_engulfing,hammer,morning_star,bullish_continuation',  strftime('%s', 'now'));
  `,
};
