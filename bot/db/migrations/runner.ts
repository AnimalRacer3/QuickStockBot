import Database from 'better-sqlite3';
import { migrations } from './index';

export function runMigrations(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS migrations (
      version    INTEGER PRIMARY KEY,
      name       TEXT    NOT NULL,
      applied_at INTEGER NOT NULL
    )
  `);

  const appliedVersions = new Set(
    (db.prepare('SELECT version FROM migrations ORDER BY version').all() as { version: number }[]).map(
      (r) => r.version,
    ),
  );

  const insert = db.prepare(
    'INSERT INTO migrations (version, name, applied_at) VALUES (?, ?, ?)',
  );

  for (const migration of migrations) {
    if (appliedVersions.has(migration.version)) continue;
    db.exec(migration.sql);
    insert.run(migration.version, migration.name, Math.floor(Date.now() / 1000));
  }
}
