import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';

function freshDb(): Database.Database {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  return db;
}

describe('Migration runner', () => {
  it('creates all expected tables on a fresh database', () => {
    const db = freshDb();
    runMigrations(db);

    const tables = (
      db.prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").all() as {
        name: string;
      }[]
    ).map((r) => r.name);

    expect(tables).toEqual(
      expect.arrayContaining([
        'migrations',
        'settings',
        'active_tickers',
        'orders',
        'order_status_events',
        'trades',
        'log_events',
        'lists',
        'ml_samples',
      ]),
    );
    db.close();
  });

  it('records migration entry with correct version and name', () => {
    const db = freshDb();
    runMigrations(db);

    const rows = db.prepare('SELECT version, name FROM migrations ORDER BY version').all() as {
      version: number;
      name: string;
    }[];

    expect(rows.length).toBeGreaterThanOrEqual(1);
    expect(rows[0]).toMatchObject({ version: 1, name: '001_initial_schema' });
    db.close();
  });

  it('migration applied_at uses second-level timestamp', () => {
    const before = Math.floor(Date.now() / 1000);
    const db = freshDb();
    runMigrations(db);
    const after = Math.floor(Date.now() / 1000);

    const row = db.prepare('SELECT applied_at FROM migrations WHERE version = 1').get() as {
      applied_at: number;
    };

    expect(row.applied_at).toBeGreaterThanOrEqual(before);
    expect(row.applied_at).toBeLessThanOrEqual(after);
    expect(row.applied_at).toBeLessThan(Date.now()); // would be huge if accidentally ms
    db.close();
  });

  it('is idempotent — running twice does not duplicate records', () => {
    const db = freshDb();
    runMigrations(db);
    runMigrations(db);

    const count = (
      db.prepare('SELECT COUNT(*) as c FROM migrations').get() as { c: number }
    ).c;

    expect(count).toBe(1);
    db.close();
  });

  it('creates expected indexes', () => {
    const db = freshDb();
    runMigrations(db);

    const indexes = (
      db.prepare("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name").all() as {
        name: string;
      }[]
    ).map((r) => r.name);

    expect(indexes).toEqual(
      expect.arrayContaining([
        'idx_order_status_events_order_id',
        'idx_trades_entry_order_id',
        'idx_log_events_occurred',
        'idx_lists_symbol',
        'idx_ml_samples_trade_id',
      ]),
    );
    db.close();
  });
});
