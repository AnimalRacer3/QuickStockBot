import Database from 'better-sqlite3';
import { Setting } from '../../../shared/models';

interface SettingRow {
  key: string;
  value: string;
  updated_at: number;
}

export class SettingsRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: SettingRow): Setting {
    return { key: row.key, value: row.value, updatedAt: row.updated_at };
  }

  get(key: string): Setting | null {
    const row = this.db
      .prepare('SELECT key, value, updated_at FROM settings WHERE key = ?')
      .get(key) as SettingRow | undefined;
    return row ? this.toModel(row) : null;
  }

  getAll(): Setting[] {
    const rows = this.db
      .prepare('SELECT key, value, updated_at FROM settings ORDER BY key')
      .all() as SettingRow[];
    return rows.map((r) => this.toModel(r));
  }

  set(key: string, value: string): Setting {
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
      )
      .run(key, value, now);
    return { key, value, updatedAt: now };
  }

  delete(key: string): void {
    this.db.prepare('DELETE FROM settings WHERE key = ?').run(key);
  }
}
