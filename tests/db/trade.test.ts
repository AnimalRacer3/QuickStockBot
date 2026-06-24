import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { OrderRepository } from '../../bot/db/repositories/orderRepository';
import { TradeRepository } from '../../bot/db/repositories/tradeRepository';
import { Order } from '../../shared/models';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  const orderRepo = new OrderRepository(db);
  const tradeRepo = new TradeRepository(db);
  return { db, orderRepo, tradeRepo };
}

function makeOrder(repo: OrderRepository, overrides: Partial<Omit<Order, 'id' | 'createdAt' | 'updatedAt'>> = {}): Order {
  return repo.create({
    symbol: 'AAPL',
    side: 'buy',
    orderType: 'market',
    quantity: 10,
    status: 'filled',
    filledPrice: 150.0,
    filledQuantity: 10,
    ...overrides,
  });
}

describe('TradeRepository', () => {
  it('creates and retrieves a trade', () => {
    const { db, orderRepo, tradeRepo } = setup();
    const entry = makeOrder(orderRepo);
    const trade = tradeRepo.create({
      symbol: 'AAPL',
      entryOrderId: entry.id,
      entryPrice: 150.0,
      quantity: 10,
      fees: 0,
      status: 'open',
    });

    expect(trade.id).toBeTruthy();
    expect(trade.symbol).toBe('AAPL');
    expect(trade.status).toBe('open');

    const fetched = tradeRepo.getById(trade.id);
    expect(fetched).not.toBeNull();
    expect(fetched!.id).toBe(trade.id);
    db.close();
  });

  it('openedAt is a second-level timestamp', () => {
    const { db, orderRepo, tradeRepo } = setup();
    const entry = makeOrder(orderRepo);
    const before = Math.floor(Date.now() / 1000);
    const trade = tradeRepo.create({
      symbol: 'AAPL',
      entryOrderId: entry.id,
      entryPrice: 150.0,
      quantity: 10,
      fees: 0,
      status: 'open',
    });
    const after = Math.floor(Date.now() / 1000);
    expect(trade.openedAt).toBeGreaterThanOrEqual(before);
    expect(trade.openedAt).toBeLessThanOrEqual(after);
    expect(trade.openedAt).toBeLessThan(Date.now());
    db.close();
  });

  it('trade links to entry order via entryOrderId', () => {
    const { db, orderRepo, tradeRepo } = setup();
    const entry = makeOrder(orderRepo);
    const trade = tradeRepo.create({
      symbol: 'AAPL',
      entryOrderId: entry.id,
      entryPrice: 150.0,
      quantity: 10,
      fees: 0,
      status: 'open',
    });

    expect(trade.entryOrderId).toBe(entry.id);
    const linked = tradeRepo.getByEntryOrderId(entry.id);
    expect(linked).not.toBeNull();
    expect(linked!.id).toBe(trade.id);
    db.close();
  });

  it('close links exit order and records P/L', () => {
    const { db, orderRepo, tradeRepo } = setup();
    const entry = makeOrder(orderRepo);
    const exit = makeOrder(orderRepo, { side: 'sell', filledPrice: 165.0 });

    const trade = tradeRepo.create({
      symbol: 'AAPL',
      entryOrderId: entry.id,
      entryPrice: 150.0,
      quantity: 10,
      fees: 0,
      status: 'open',
    });

    const closed = tradeRepo.close(trade.id, exit.id, 165.0, 150.0, 149.5, 0.5);
    expect(closed.status).toBe('closed');
    expect(closed.exitOrderId).toBe(exit.id);
    expect(closed.exitPrice).toBe(165.0);
    expect(closed.grossPnl).toBe(150.0);
    expect(closed.netPnl).toBe(149.5);
    expect(closed.fees).toBe(0.5);
    expect(closed.closedAt).not.toBeNull();
    expect(closed.closedAt).toBeLessThan(Date.now());

    const linked = tradeRepo.getByExitOrderId(exit.id);
    expect(linked!.id).toBe(trade.id);
    db.close();
  });

  it('setLabel marks trade good or bad', () => {
    const { db, orderRepo, tradeRepo } = setup();
    const entry = makeOrder(orderRepo);
    const trade = tradeRepo.create({
      symbol: 'AAPL',
      entryOrderId: entry.id,
      entryPrice: 150.0,
      quantity: 10,
      fees: 0,
      status: 'open',
    });

    expect(tradeRepo.setLabel(trade.id, 'good').label).toBe('good');
    expect(tradeRepo.setLabel(trade.id, 'bad').label).toBe('bad');
    db.close();
  });

  it('getOpenTrades only returns open trades', () => {
    const { db, orderRepo, tradeRepo } = setup();
    const e1 = makeOrder(orderRepo);
    const e2 = makeOrder(orderRepo);
    const exit = makeOrder(orderRepo, { side: 'sell' });

    tradeRepo.create({ symbol: 'AAPL', entryOrderId: e1.id, entryPrice: 150, quantity: 10, fees: 0, status: 'open' });
    const t2 = tradeRepo.create({ symbol: 'AAPL', entryOrderId: e2.id, entryPrice: 150, quantity: 10, fees: 0, status: 'open' });
    tradeRepo.close(t2.id, exit.id, 155, 50, 49.5, 0.5);

    const open = tradeRepo.getOpenTrades();
    expect(open.length).toBe(1);
    expect(open[0].status).toBe('open');
    db.close();
  });

  it('FK constraint rejects an invalid entry_order_id', () => {
    const { db, tradeRepo } = setup();
    expect(() =>
      tradeRepo.create({
        symbol: 'AAPL',
        entryOrderId: '00000000-0000-0000-0000-000000000000',
        entryPrice: 150,
        quantity: 10,
        fees: 0,
        status: 'open',
      }),
    ).toThrow();
    db.close();
  });
});
