import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { DailyEfficiencyRepository } from '../../bot/db/repositories/dailyEfficiencyRepository';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new DailyEfficiencyRepository(db) };
}

describe('DailyEfficiencyRepository', () => {
  it('returns null for a missing date', () => {
    const { db, repo } = setup();
    expect(repo.getByDate('2024-01-01')).toBeNull();
    db.close();
  });

  it('upsert creates a record', () => {
    const { db, repo } = setup();
    const rec = repo.upsert({
      date: '2024-01-02',
      tradesToGoal: 3,
      goalReached: true,
      dailyPnlPct: 2.4,
    });

    expect(rec.date).toBe('2024-01-02');
    expect(rec.tradesToGoal).toBe(3);
    expect(rec.goalReached).toBe(true);
    expect(rec.dailyPnlPct).toBeCloseTo(2.4);
    db.close();
  });

  it('upsert overwrites an existing record for the same date', () => {
    const { db, repo } = setup();
    repo.upsert({ date: '2024-01-02', tradesToGoal: 5, goalReached: false, dailyPnlPct: 1.0 });
    const updated = repo.upsert({ date: '2024-01-02', tradesToGoal: 2, goalReached: true, dailyPnlPct: 3.0 });

    expect(updated.tradesToGoal).toBe(2);
    expect(updated.goalReached).toBe(true);
    expect(updated.dailyPnlPct).toBeCloseTo(3.0);
    db.close();
  });

  it('getAll returns records in ascending date order', () => {
    const { db, repo } = setup();
    repo.upsert({ date: '2024-01-03', tradesToGoal: 1, goalReached: true, dailyPnlPct: 5.0 });
    repo.upsert({ date: '2024-01-01', tradesToGoal: 4, goalReached: false, dailyPnlPct: 1.0 });
    repo.upsert({ date: '2024-01-02', tradesToGoal: 2, goalReached: true, dailyPnlPct: 2.5 });

    const all = repo.getAll();
    expect(all.map((r) => r.date)).toEqual(['2024-01-01', '2024-01-02', '2024-01-03']);
    db.close();
  });

  it('getRecent returns the N most recent records newest first', () => {
    const { db, repo } = setup();
    repo.upsert({ date: '2024-01-01', tradesToGoal: 3, goalReached: true, dailyPnlPct: 2.0 });
    repo.upsert({ date: '2024-01-02', tradesToGoal: 2, goalReached: true, dailyPnlPct: 3.0 });
    repo.upsert({ date: '2024-01-03', tradesToGoal: 5, goalReached: false, dailyPnlPct: 0.5 });

    const recent = repo.getRecent(2);
    expect(recent.length).toBe(2);
    expect(recent[0].date).toBe('2024-01-03');
    expect(recent[1].date).toBe('2024-01-02');
    db.close();
  });

  it('hitRate returns 0 when no records', () => {
    const { db, repo } = setup();
    expect(repo.hitRate()).toBeCloseTo(0.0);
    db.close();
  });

  it('hitRate computes fraction of goal-reached days', () => {
    const { db, repo } = setup();
    repo.upsert({ date: '2024-01-01', tradesToGoal: 1, goalReached: true, dailyPnlPct: 2.5 });
    repo.upsert({ date: '2024-01-02', tradesToGoal: 5, goalReached: false, dailyPnlPct: 0.8 });
    repo.upsert({ date: '2024-01-03', tradesToGoal: 2, goalReached: true, dailyPnlPct: 3.0 });

    expect(repo.hitRate()).toBeCloseTo(2 / 3);
    db.close();
  });

  it('recordedAt is a second-level unix timestamp', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const rec = repo.upsert({
      date: '2024-01-02',
      tradesToGoal: 1,
      goalReached: true,
      dailyPnlPct: 2.5,
    });
    const after = Math.floor(Date.now() / 1000);

    expect(rec.recordedAt).toBeGreaterThanOrEqual(before);
    expect(rec.recordedAt).toBeLessThanOrEqual(after);
    expect(rec.recordedAt).toBeLessThan(Date.now());
    db.close();
  });

  it('goalReached false is stored and retrieved correctly', () => {
    const { db, repo } = setup();
    const rec = repo.upsert({
      date: '2024-01-05',
      tradesToGoal: 8,
      goalReached: false,
      dailyPnlPct: -0.5,
    });
    expect(rec.goalReached).toBe(false);
    expect(repo.getByDate('2024-01-05')!.goalReached).toBe(false);
    db.close();
  });
});
