import Database from "better-sqlite3";
import path from "path";

const DB_PATH = process.env.LICENSE_DB_PATH ?? path.join(process.cwd(), "licenses.db");

let _db: Database.Database | null = null;

export function getLicenseDb(): Database.Database {
  if (!_db) {
    _db = openDb(DB_PATH);
  }
  return _db;
}

/** Creates an independent in-memory DB instance — use in tests. */
export function createDb(filePath = ":memory:"): Database.Database {
  return openDb(filePath);
}

function openDb(filePath: string): Database.Database {
  const db = new Database(filePath);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  migrate(db);
  return db;
}

function migrate(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS licenses (
      key        TEXT PRIMARY KEY,
      user_id    TEXT NOT NULL,
      status     TEXT NOT NULL DEFAULT 'active',
      issued_at  TEXT NOT NULL,
      expires_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_licenses_user_id ON licenses(user_id);
    CREATE INDEX IF NOT EXISTS idx_licenses_status  ON licenses(status);
  `);
}
