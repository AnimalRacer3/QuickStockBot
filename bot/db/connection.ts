import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';

export function openDatabase(
  dbPath: string = path.join(process.cwd(), 'data', 'quickstock.db'),
): Database.Database {
  if (dbPath !== ':memory:') {
    const dir = path.dirname(dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  return db;
}
