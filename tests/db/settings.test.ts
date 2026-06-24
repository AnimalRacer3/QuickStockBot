import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { seedDefaults } from '../../bot/db/seed';
import { SettingsRepository } from '../../bot/db/repositories/settingsRepository';
import { DEFAULT_SETTINGS } from '../../shared/models';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new SettingsRepository(db) };
}

describe('SettingsRepository', () => {
  it('sets and retrieves a value', () => {
    const { db, repo } = setup();
    const s = repo.set('max_position_size', '500');
    expect(s).toMatchObject({ key: 'max_position_size', value: '500' });
    expect(repo.get('max_position_size')).toMatchObject({ value: '500' });
    db.close();
  });

  it('returns null for an unknown key', () => {
    const { db, repo } = setup();
    expect(repo.get('does_not_exist')).toBeNull();
    db.close();
  });

  it('overwrites an existing value', () => {
    const { db, repo } = setup();
    repo.set('stop_loss_pct', '0.03');
    repo.set('stop_loss_pct', '0.07');
    expect(repo.get('stop_loss_pct')!.value).toBe('0.07');
    db.close();
  });

  it('getAll returns every setting ordered by key', () => {
    const { db, repo } = setup();
    repo.set('beta', 'b');
    repo.set('alpha', 'a');
    const all = repo.getAll();
    expect(all.map((s) => s.key)).toEqual(['alpha', 'beta']);
    db.close();
  });

  it('delete removes a setting', () => {
    const { db, repo } = setup();
    repo.set('temp', '1');
    repo.delete('temp');
    expect(repo.get('temp')).toBeNull();
    db.close();
  });

  it('updatedAt is a second-level Unix timestamp', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const s = repo.set('key', 'val');
    const after = Math.floor(Date.now() / 1000);
    expect(s.updatedAt).toBeGreaterThanOrEqual(before);
    expect(s.updatedAt).toBeLessThanOrEqual(after);
    expect(s.updatedAt).toBeLessThan(Date.now());
    db.close();
  });

  it('seedDefaults inserts all DEFAULT_SETTINGS', () => {
    const { db, repo } = setup();
    seedDefaults(db);
    const all = repo.getAll();
    expect(all.length).toBe(Object.keys(DEFAULT_SETTINGS).length);
    expect(repo.get('max_position_size')!.value).toBe(DEFAULT_SETTINGS['max_position_size']);
    expect(repo.get('paper_trading')!.value).toBe('true');
    db.close();
  });

  it('seedDefaults does not overwrite pre-existing values', () => {
    const { db, repo } = setup();
    repo.set('max_position_size', '9999');
    seedDefaults(db);
    expect(repo.get('max_position_size')!.value).toBe('9999');
    db.close();
  });

  it('seedDefaults is idempotent', () => {
    const { db, repo } = setup();
    seedDefaults(db);
    seedDefaults(db);
    expect(repo.getAll().length).toBe(Object.keys(DEFAULT_SETTINGS).length);
    db.close();
  });
});
