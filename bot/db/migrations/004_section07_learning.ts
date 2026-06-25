export const migration004 = {
  version: 4,
  name: '004_section07_learning',
  sql: `
    -- Per-ticker cumulative profit/loss statistics for the scanner's prior-profit bias.
    -- Updated on every round-trip completion; read by the scanner to bias high-P/L tickers.
    CREATE TABLE ticker_profit_stats (
      symbol          TEXT    PRIMARY KEY,
      cumulative_pnl  REAL    NOT NULL DEFAULT 0.0,
      trade_count     INTEGER NOT NULL DEFAULT 0,
      win_count       INTEGER NOT NULL DEFAULT 0,
      updated_at      INTEGER NOT NULL
    );

    -- Per-day efficiency records for the conviction-threshold tuner.
    CREATE TABLE daily_efficiency (
      date            TEXT    PRIMARY KEY,  -- YYYY-MM-DD
      trades_to_goal  INTEGER NOT NULL,
      goal_reached    INTEGER NOT NULL DEFAULT 0,
      daily_pnl_pct   REAL    NOT NULL DEFAULT 0.0,
      recorded_at     INTEGER NOT NULL
    );

    -- Section-7 learning settings
    INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
      ('ml_conviction_threshold',    '0.6',                strftime('%s', 'now')),
      ('ml_algorithm',               'gradient_boosting',  strftime('%s', 'now')),
      ('ml_model_version',           '',                   strftime('%s', 'now')),
      ('ml_models_dir',              'models',             strftime('%s', 'now')),
      ('daily_profit_target_pct',    '2.0',                strftime('%s', 'now')),
      ('daily_max_loss_pct',         '-2.0',               strftime('%s', 'now')),
      ('risk_per_trade_pct',         '0.5',                strftime('%s', 'now')),
      ('ml_min_hit_rate',            '0.5',                strftime('%s', 'now'));

    CREATE INDEX idx_ticker_profit_stats_pnl ON ticker_profit_stats(cumulative_pnl);
    CREATE INDEX idx_daily_efficiency_date   ON daily_efficiency(date);
  `,
};
