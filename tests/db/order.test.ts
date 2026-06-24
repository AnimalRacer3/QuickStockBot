import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { OrderRepository } from '../../bot/db/repositories/orderRepository';
import { Order } from '../../shared/models';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return { db, repo: new OrderRepository(db) };
}

const baseInput = (): Omit<Order, 'id' | 'createdAt' | 'updatedAt'> => ({
  symbol: 'AAPL',
  side: 'buy',
  orderType: 'market',
  quantity: 10,
  status: 'pending',
});

describe('OrderRepository', () => {
  it('creates an order and retrieves it by id', () => {
    const { db, repo } = setup();
    const o = repo.create(baseInput());
    expect(o.id).toBeTruthy();
    expect(o.symbol).toBe('AAPL');
    expect(o.status).toBe('pending');

    const fetched = repo.getById(o.id);
    expect(fetched).not.toBeNull();
    expect(fetched!.id).toBe(o.id);
    db.close();
  });

  it('createdAt and updatedAt are second-level timestamps', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const o = repo.create(baseInput());
    const after = Math.floor(Date.now() / 1000);

    expect(o.createdAt).toBeGreaterThanOrEqual(before);
    expect(o.createdAt).toBeLessThanOrEqual(after);
    expect(o.createdAt).toBeLessThan(Date.now()); // would be ms-scale if wrong precision
    expect(o.updatedAt).toBe(o.createdAt);
    db.close();
  });

  it('returns null for an unknown id', () => {
    const { db, repo } = setup();
    expect(repo.getById('00000000-0000-0000-0000-000000000000')).toBeNull();
    db.close();
  });

  it('updateStatus transitions status and records event', () => {
    const { db, repo } = setup();
    const o = repo.create(baseInput());
    const opened = repo.updateStatus(o.id, 'open');
    expect(opened.status).toBe('open');

    const filled = repo.updateStatus(o.id, 'filled', 150.25, 10);
    expect(filled.status).toBe('filled');
    expect(filled.filledPrice).toBe(150.25);
    expect(filled.filledQuantity).toBe(10);
    db.close();
  });

  it('getStatusHistory is ordered chronologically oldest-first', () => {
    const { db, repo } = setup();
    const o = repo.create(baseInput()); // pending
    repo.updateStatus(o.id, 'open');
    repo.updateStatus(o.id, 'partial', 150.0, 5);
    repo.updateStatus(o.id, 'filled', 151.0, 10);

    const history = repo.getStatusHistory(o.id);
    expect(history.length).toBe(4);
    expect(history.map((e) => e.status)).toEqual(['pending', 'open', 'partial', 'filled']);
    db.close();
  });

  it('status event occurredAt is a second-level timestamp', () => {
    const { db, repo } = setup();
    const before = Math.floor(Date.now() / 1000);
    const o = repo.create(baseInput());
    const after = Math.floor(Date.now() / 1000);

    const [event] = repo.getStatusHistory(o.id);
    expect(event.occurredAt).toBeGreaterThanOrEqual(before);
    expect(event.occurredAt).toBeLessThanOrEqual(after);
    expect(event.occurredAt).toBeLessThan(Date.now());
    db.close();
  });

  it('create auto-inserts initial status event', () => {
    const { db, repo } = setup();
    const o = repo.create(baseInput());
    const history = repo.getStatusHistory(o.id);
    expect(history.length).toBe(1);
    expect(history[0].status).toBe('pending');
    db.close();
  });

  it('getBySymbol filters by symbol', () => {
    const { db, repo } = setup();
    repo.create(baseInput());
    repo.create({ ...baseInput(), symbol: 'TSLA' });
    const appleOrders = repo.getBySymbol('AAPL');
    expect(appleOrders.length).toBe(1);
    expect(appleOrders[0].symbol).toBe('AAPL');
    db.close();
  });

  it('stores optional limit and stop prices', () => {
    const { db, repo } = setup();
    const o = repo.create({
      ...baseInput(),
      orderType: 'limit',
      limitPrice: 148.0,
      stopPrice: 145.0,
    });
    const fetched = repo.getById(o.id)!;
    expect(fetched.limitPrice).toBe(148.0);
    expect(fetched.stopPrice).toBe(145.0);
    db.close();
  });
});
