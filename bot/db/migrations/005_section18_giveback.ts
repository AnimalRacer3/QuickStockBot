export const migration005 = {
  version: 5,
  name: '005_section18_giveback',
  sql: `
    INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
      ('daily_target_mode',  'giveback', strftime('%s', 'now')),
      ('daily_giveback_pct', '25.0',     strftime('%s', 'now'));
  `,
};
