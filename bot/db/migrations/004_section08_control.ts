export const migration004 = {
  version: 4,
  name: '004_section08_control',
  sql: `
    CREATE TABLE run_days (
      date       TEXT    PRIMARY KEY,
      marked_at  INTEGER NOT NULL
    );

    INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
      ('daily_risk_pct',        '5.0',   strftime('%s', 'now')),
      ('risk_override_enabled', 'false', strftime('%s', 'now')),
      ('risk_per_trade_pct',    '1.0',   strftime('%s', 'now')),
      ('max_positions',         '5',     strftime('%s', 'now'));
  `,
};
