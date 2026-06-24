import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { ListRepository } from '../../bot/db/repositories/listRepository';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new ListRepository(db) };
}

describe('ListRepository', () => {
  it('adds and retrieves a whitelist entry', () => {
    const { db, repo } = setup();
    const e = repo.add({ symbol: 'AAPL', listType: 'whitelist', active: true });
    expect(e.id).toBeGreaterThan(0);
    expect(e.symbol).toBe('AAPL');
    expect(e.listType).toBe('whitelist');
    expect(e.active).toBe(true);
    expect(e.addedAt).toBeLessThan(Date.now());

    const fetched = repo.getBySymbol('AAPL');
    expect(fetched.length).toBe(1);
    db.close();
  });

  it('adds a blacklist entry with a reason', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'GME', listType: 'blacklist', reason: 'too volatile', active: true });
    const [e] = repo.getByType('blacklist');
    expect(e.symbol).toBe('GME');
    expect(e.reason).toBe('too volatile');
    db.close();
  });

  it('isListed returns true only for the correct list type', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'AAPL', listType: 'whitelist', active: true });
    expect(repo.isListed('AAPL', 'whitelist')).toBe(true);
    expect(repo.isListed('AAPL', 'blacklist')).toBe(false);
    db.close();
  });

  it('deactivate makes isListed return false', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'AAPL', listType: 'whitelist', active: true });
    repo.deactivate('AAPL', 'whitelist');
    expect(repo.isListed('AAPL', 'whitelist')).toBe(false);
    const entries = repo.getBySymbol('AAPL');
    expect(entries[0].active).toBe(false);
    db.close();
  });

  it('remove deletes the entry entirely', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'AAPL', listType: 'whitelist', active: true });
    repo.remove('AAPL', 'whitelist');
    expect(repo.getBySymbol('AAPL').length).toBe(0);
    expect(repo.isListed('AAPL', 'whitelist')).toBe(false);
    db.close();
  });

  it('same symbol can appear in both lists independently', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'AAPL', listType: 'whitelist', active: true });
    repo.add({ symbol: 'AAPL', listType: 'blacklist', active: true });
    expect(repo.isListed('AAPL', 'whitelist')).toBe(true);
    expect(repo.isListed('AAPL', 'blacklist')).toBe(true);
    expect(repo.getBySymbol('AAPL').length).toBe(2);
    db.close();
  });

  it('upserts on conflict (same symbol+listType updates in place)', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'MSFT', listType: 'whitelist', reason: 'original', active: true });
    repo.add({ symbol: 'MSFT', listType: 'whitelist', reason: 'updated', active: false });
    const entries = repo.getBySymbol('MSFT');
    expect(entries.length).toBe(1);
    expect(entries[0].reason).toBe('updated');
    expect(entries[0].active).toBe(false);
    db.close();
  });

  it('getByType returns only that type', () => {
    const { db, repo } = setup();
    repo.add({ symbol: 'AAPL', listType: 'whitelist', active: true });
    repo.add({ symbol: 'GME', listType: 'blacklist', active: true });
    repo.add({ symbol: 'TSLA', listType: 'whitelist', active: true });

    const white = repo.getByType('whitelist');
    expect(white.length).toBe(2);
    expect(white.every((e) => e.listType === 'whitelist')).toBe(true);
    db.close();
  });
});
