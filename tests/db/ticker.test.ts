import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { TickerRepository } from '../../bot/db/repositories/tickerRepository';
import { ActiveTicker } from '../../shared/models';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new TickerRepository(db) };
}

const base: ActiveTicker = {
  symbol: 'AAPL',
  price: 150.25,
  volume: 1_000_000,
  rsi: 45.5,
  macd: 0.12,
  signal: 0.10,
  emaShort: 149.5,
  emaLong: 148.0,
  state: 'watching',
  updatedAt: 0,
};

describe('TickerRepository', () => {
  it('upserts and retrieves a ticker', () => {
    const { db, repo } = setup();
    repo.upsert(base);
    const t = repo.getBySymbol('AAPL');
    expect(t).not.toBeNull();
    expect(t!.symbol).toBe('AAPL');
    expect(t!.price).toBe(150.25);
    expect(t!.state).toBe('watching');
    db.close();
  });

  it('upsert updates existing ticker in place', () => {
    const { db, repo } = setup();
    repo.upsert(base);
    repo.upsert({ ...base, price: 200.0, state: 'holding' });
    const t = repo.getBySymbol('AAPL');
    expect(t!.price).toBe(200.0);
    expect(t!.state).toBe('holding');
    expect(repo.getAll().length).toBe(1);
    db.close();
  });

  it('returns null for unknown symbol', () => {
    const { db, repo } = setup();
    expect(repo.getBySymbol('UNKNOWN')).toBeNull();
    db.close();
  });

  it('getAll returns every ticker ordered by symbol', () => {
    const { db, repo } = setup();
    repo.upsert({ ...base, symbol: 'TSLA' });
    repo.upsert(base);
    const all = repo.getAll();
    expect(all.map((t) => t.symbol)).toEqual(['AAPL', 'TSLA']);
    db.close();
  });

  it('delete removes a ticker', () => {
    const { db, repo } = setup();
    repo.upsert(base);
    repo.delete('AAPL');
    expect(repo.getBySymbol('AAPL')).toBeNull();
    db.close();
  });

  it('stores and retrieves null optional fields', () => {
    const { db, repo } = setup();
    repo.upsert({ ...base, rsi: null, macd: null, signal: null, emaShort: null, emaLong: null });
    const t = repo.getBySymbol('AAPL');
    expect(t!.rsi).toBeNull();
    expect(t!.macd).toBeNull();
    expect(t!.emaShort).toBeNull();
    db.close();
  });

  it('updatedAt is refreshed on upsert to a second-level timestamp', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const saved = repo.upsert(base);
    const after = Math.floor(Date.now() / 1000);
    expect(saved.updatedAt).toBeGreaterThanOrEqual(before);
    expect(saved.updatedAt).toBeLessThanOrEqual(after);
    expect(saved.updatedAt).toBeLessThan(Date.now());
    db.close();
  });

  it('supports all three state values', () => {
    const { db, repo } = setup();
    for (const state of ['watching', 'holding', 'idle'] as const) {
      repo.upsert({ ...base, state });
      expect(repo.getBySymbol('AAPL')!.state).toBe(state);
    }
    db.close();
  });
});
