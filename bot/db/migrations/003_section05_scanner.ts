export const migration003 = {
  version: 3,
  name: '003_section05_scanner',
  sql: `
    -- Extend active_tickers with Section-5 scanner state columns
    ALTER TABLE active_tickers ADD COLUMN gap_pct         REAL;
    ALTER TABLE active_tickers ADD COLUMN rvol            REAL;
    ALTER TABLE active_tickers ADD COLUMN float_shares    INTEGER;
    ALTER TABLE active_tickers ADD COLUMN unknown_float   INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE active_tickers ADD COLUMN scanner_tradable INTEGER NOT NULL DEFAULT 1;
    ALTER TABLE active_tickers ADD COLUMN pct_change      REAL;
    ALTER TABLE active_tickers ADD COLUMN macd_state_json TEXT;
    ALTER TABLE active_tickers ADD COLUMN pattern_tags_json TEXT;
    ALTER TABLE active_tickers ADD COLUMN pattern_sig_json  TEXT;
    ALTER TABLE active_tickers ADD COLUMN role            TEXT;
    ALTER TABLE active_tickers ADD COLUMN score           REAL;

    -- Section-5 scanner settings
    INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
      ('pre_open_lead_hours',        '1.0',   strftime('%s', 'now')),
      ('scan_duration_hours',        '3.0',   strftime('%s', 'now')),
      ('scanner_refresh_seconds',    '60',    strftime('%s', 'now')),
      ('min_price',                  '1.0',   strftime('%s', 'now')),
      ('max_price',                  '20.0',  strftime('%s', 'now')),
      ('gap_up_min_pct',             '5.0',   strftime('%s', 'now')),
      ('relative_volume_min',        '2.0',   strftime('%s', 'now')),
      ('max_float_shares',           '20000000', strftime('%s', 'now')),
      ('require_news',               'true',  strftime('%s', 'now')),
      ('include_unknown_float',      'true',  strftime('%s', 'now')),
      ('active_tickers_n',           '3',     strftime('%s', 'now')),
      ('prior_profit_bias_weight',   '0.5',   strftime('%s', 'now')),
      ('leader_similarity_threshold','0.7',   strftime('%s', 'now'));
  `,
};
