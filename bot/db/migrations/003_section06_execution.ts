export const migration003 = {
  version: 3,
  name: '003_section06_execution',
  sql: `
    -- Remove old max_trades_per_day setting if present
    DELETE FROM settings WHERE key = 'max_trades_per_day';

    INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
      ('active_tickers_n',             '10',          strftime('%s', 'now')),
      ('stop_loss_pct',                '1.0',         strftime('%s', 'now')),
      ('take_profit_pct',              '3.0',         strftime('%s', 'now')),
      ('daily_max_loss_pct',           '-2.0',        strftime('%s', 'now')),
      ('daily_profit_target_pct',      '3.0',         strftime('%s', 'now')),
      ('flatten_on_max_loss',          'true',        strftime('%s', 'now')),
      ('flatten_on_profit_target',     'false',       strftime('%s', 'now')),
      ('position_size_pct',            '25.0',        strftime('%s', 'now')),
      ('override_risk_per_trade',      'false',       strftime('%s', 'now')),
      ('exit_mode',                    'dump',        strftime('%s', 'now')),
      ('trail_off_trigger',            'per_candle',  strftime('%s', 'now')),
      ('trail_off_fraction_per_candle','0.25',        strftime('%s', 'now')),
      ('trailing_stop',                'false',       strftime('%s', 'now')),
      ('trailing_stop_pct',            '1.0',         strftime('%s', 'now')),
      ('force_close_at_close',         'true',        strftime('%s', 'now')),
      ('z_hour_cutoff',                '1.0',         strftime('%s', 'now')),
      ('conviction_threshold',         '0.6',         strftime('%s', 'now')),
      ('min_account_equity_notice',    '2000.0',      strftime('%s', 'now'));
  `,
};
