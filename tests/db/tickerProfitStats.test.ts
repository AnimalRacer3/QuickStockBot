import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { TickerProfitStatsRepository } from '../../bot/db/repositories/tickerProfitStatsRepository';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new TickerProfitStatsRepository(db) };
}

describe('TickerProfitStatsRepository', () => {
  it('returns null for an unknown symbol', () => {
    const { db, repo } = setup();
    expect(repo.getBySymbol('UNKNOWN')).toBeNull();
    db.close();
  });

  it('recordTrade creates an entry for a new symbol', () => {
    const { db, repo } = setup();
    const stats = repo.recordTrade('AAPL', 150.0);
    expect(stats.symbol).toBe('AAPL');
    expect(stats.cumulativePnl).toBeCloseTo(150.0);
    expect(stats.tradeCount).toBe(1);
    expect(stats.winCount).toBe(1);
    expect(stats.winRate).toBeCloseTo(1.0);
    db.close();
  });

  it('recordTrade updates an existing entry', () => {
    const { db, repo } = setup();
    repo.recordTrade('AAPL', 100.0);
    repo.recordTrade('AAPL', -40.0);
    const stats = repo.recordTrade('AAPL', 200.0);

    expect(stats.cumulativePnl).toBeCloseTo(260.0);
    expect(stats.tradeCount).toBe(3);
    expect(stats.winCount).toBe(2);
    expect(stats.winRate).toBeCloseTo(2 / 3);
    db.close();
  });

  it('losing trade increments trade_count but not win_count', () => {
    const { db, repo } = setup();
    const stats = repo.recordTrade('TSLA', -75.0);
    expect(stats.tradeCount).toBe(1);
    expect(stats.winCount).toBe(0);
    expect(stats.winRate).toBeCloseTo(0.0);
    db.close();
  });

  it('getAll returns all symbols sorted by cumulative_pnl descending', () => {
    const { db, repo } = setup();
    repo.recordTrade('AAPL', 500.0);
    repo.recordTrade('TSLA', -100.0);
    repo.recordTrade('NVDA', 300.0);

    const all = repo.getAll();
    expect(all.length).toBe(3);
    expect(all[0].symbol).toBe('AAPL');  // highest P/L
    expect(all[1].symbol).toBe('NVDA');
    expect(all[2].symbol).toBe('TSLA');
    db.close();
  });

  it('reset zeros out a symbol stats', () => {
    const { db, repo } = setup();
    repo.recordTrade('AAPL', 500.0);
    repo.recordTrade('AAPL', 200.0);
    repo.reset('AAPL');

    const stats = repo.getBySymbol('AAPL');
    expect(stats).not.toBeNull();
    expect(stats!.cumulativePnl).toBeCloseTo(0.0);
    expect(stats!.tradeCount).toBe(0);
    expect(stats!.winCount).toBe(0);
    db.close();
  });

  it('reset creates an entry for an unknown symbol', () => {
    const { db, repo } = setup();
    repo.reset('NEW');
    const stats = repo.getBySymbol('NEW');
    expect(stats).not.toBeNull();
    expect(stats!.cumulativePnl).toBeCloseTo(0.0);
    db.close();
  });

  it('multiple symbols are tracked independently', () => {
    const { db, repo } = setup();
    repo.recordTrade('AAPL', 100.0);
    repo.recordTrade('TSLA', -50.0);
    repo.recordTrade('NVDA', 300.0);

    expect(repo.getBySymbol('AAPL')!.cumulativePnl).toBeCloseTo(100.0);
    expect(repo.getBySymbol('TSLA')!.cumulativePnl).toBeCloseTo(-50.0);
    expect(repo.getBySymbol('NVDA')!.cumulativePnl).toBeCloseTo(300.0);
    db.close();
  });

  it('updatedAt is a second-level unix timestamp', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const stats = repo.recordTrade('AAPL', 50.0);
    const after = Math.floor(Date.now() / 1000);

    expect(stats.updatedAt).toBeGreaterThanOrEqual(before);
    expect(stats.updatedAt).toBeLessThanOrEqual(after);
    expect(stats.updatedAt).toBeLessThan(Date.now()); // not in ms
    db.close();
  });
});
