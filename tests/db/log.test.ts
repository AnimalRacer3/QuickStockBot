import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { LogRepository } from '../../bot/db/repositories/logRepository';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new LogRepository(db) };
}

describe('LogRepository', () => {
  it('inserts and returns a log event with an auto id', () => {
    const { db, repo } = setup();
    const now = Math.floor(Date.now() / 1000);
    const e = repo.insert({ level: 'info', message: 'hello', occurredAt: now });
    expect(e.id).toBeGreaterThan(0);
    expect(e.level).toBe('info');
    expect(e.message).toBe('hello');
    db.close();
  });

  it('occurredAt is stored at second-level precision', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const e = repo.insert({ level: 'debug', message: 'ts check', occurredAt: before });
    const after = Math.floor(Date.now() / 1000);
    expect(e.occurredAt).toBeGreaterThanOrEqual(before);
    expect(e.occurredAt).toBeLessThanOrEqual(after);
    expect(e.occurredAt).toBeLessThan(Date.now());
    db.close();
  });

  it('stores and round-trips JSON context', () => {
    const { db, repo } = setup();
    const ctx = { symbol: 'AAPL', price: 150.5, nested: { ok: true } };
    repo.insert({ level: 'warn', message: 'ctx test', context: ctx, occurredAt: Math.floor(Date.now() / 1000) });
    const [e] = repo.getRecent(1);
    expect(e.context).toEqual(ctx);
    db.close();
  });

  it('getRecent respects the limit and returns most-recent first', () => {
    const { db, repo } = setup();
    const now = Math.floor(Date.now() / 1000);
    for (let i = 0; i < 5; i++) {
      repo.insert({ level: 'info', message: `msg-${i}`, occurredAt: now + i });
    }
    const recent = repo.getRecent(3);
    expect(recent.length).toBe(3);
    expect(recent[0].message).toBe('msg-4');
    expect(recent[2].message).toBe('msg-2');
    db.close();
  });

  it('getByLevel filters to correct level', () => {
    const { db, repo } = setup();
    const now = Math.floor(Date.now() / 1000);
    repo.insert({ level: 'info', message: 'info', occurredAt: now });
    repo.insert({ level: 'error', message: 'err1', occurredAt: now });
    repo.insert({ level: 'error', message: 'err2', occurredAt: now + 1 });

    const errors = repo.getByLevel('error');
    expect(errors.length).toBe(2);
    expect(errors.every((e) => e.level === 'error')).toBe(true);
    db.close();
  });

  it('supports all four log levels', () => {
    const { db, repo } = setup();
    const now = Math.floor(Date.now() / 1000);
    const levels: Array<'debug' | 'info' | 'warn' | 'error'> = ['debug', 'info', 'warn', 'error'];
    for (const level of levels) repo.insert({ level, message: level, occurredAt: now });
    const all = repo.getRecent(100);
    expect(all.length).toBe(4);
    db.close();
  });

  it('null context is preserved', () => {
    const { db, repo } = setup();
    const now = Math.floor(Date.now() / 1000);
    repo.insert({ level: 'info', message: 'no ctx', occurredAt: now });
    const [e] = repo.getRecent(1);
    expect(e.context).toBeNull();
    db.close();
  });
});
