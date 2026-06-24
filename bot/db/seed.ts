import Database from 'better-sqlite3';
import { DEFAULT_SETTINGS } from '../../shared/models';

export function seedDefaults(db: Database.Database): void {
  const now = Math.floor(Date.now() / 1000);
  const upsert = db.prepare(
    'INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
  );
  db.transaction(() => {
    for (const [key, value] of Object.entries(DEFAULT_SETTINGS)) {
      upsert.run(key, value, now);
    }
  })();
}
