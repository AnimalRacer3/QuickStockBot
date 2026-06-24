import Database from 'better-sqlite3';
import { runMigrations } from '../../bot/db/migrations/runner';
import { OrderRepository } from '../../bot/db/repositories/orderRepository';
import { TradeRepository } from '../../bot/db/repositories/tradeRepository';
import { MlSampleRepository } from '../../bot/db/repositories/mlSampleRepository';

function setup() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return {
    db,
    orderRepo: new OrderRepository(db),
    tradeRepo: new TradeRepository(db),
    repo: new MlSampleRepository(db),
  };
}

const now = () => Math.floor(Date.now() / 1000);

describe('MlSampleRepository', () => {
  it('inserts and retrieves a sample with an auto id', () => {
    const { db, repo } = setup();
    const s = repo.insert({ symbol: 'AAPL', features: { rsi: 45.5, macd: 0.12 }, sampledAt: now() });
    expect(s.id).toBeGreaterThan(0);
    expect(s.symbol).toBe('AAPL');
    expect(s.label).toBeNull();

    const fetched = repo.getById(s.id!);
    expect(fetched).not.toBeNull();
    expect(fetched!.features).toEqual({ rsi: 45.5, macd: 0.12 });
    db.close();
  });

  it('sampledAt is preserved exactly', () => {
    const { db, repo } = setup();
    const ts = now();
    const s = repo.insert({ symbol: 'AAPL', features: { rsi: 30 }, sampledAt: ts });
    expect(s.sampledAt).toBe(ts);
    expect(s.sampledAt).toBeLessThan(Date.now());
    db.close();
  });

  it('setLabel assigns 1 (good) or 0 (bad)', () => {
    const { db, repo } = setup();
    const s = repo.insert({ symbol: 'AAPL', features: { rsi: 30 }, sampledAt: now() });
    expect(repo.setLabel(s.id!, 1).label).toBe(1);
    expect(repo.setLabel(s.id!, 0).label).toBe(0);
    db.close();
  });

  it('getUnlabeled returns only null-label samples', () => {
    const { db, repo } = setup();
    const s1 = repo.insert({ symbol: 'AAPL', features: { rsi: 30 }, sampledAt: now() });
    repo.insert({ symbol: 'TSLA', features: { rsi: 70 }, sampledAt: now() });
    repo.setLabel(s1.id!, 0);

    const unlabeled = repo.getUnlabeled();
    expect(unlabeled.length).toBe(1);
    expect(unlabeled[0].symbol).toBe('TSLA');
    db.close();
  });

  it('stores and round-trips model version', () => {
    const { db, repo } = setup();
    const s = repo.insert({ symbol: 'AAPL', features: { rsi: 45 }, modelVersion: 'v1.2.3', sampledAt: now() });
    expect(repo.getById(s.id!)!.modelVersion).toBe('v1.2.3');
    db.close();
  });

  it('links sample to a trade via tradeId', () => {
    const { db, orderRepo, tradeRepo, repo } = setup();
    const order = orderRepo.create({
      symbol: 'AAPL', side: 'buy', orderType: 'market',
      quantity: 10, status: 'filled',
    });
    const trade = tradeRepo.create({
      symbol: 'AAPL', entryOrderId: order.id, entryPrice: 150,
      quantity: 10, fees: 0, status: 'open',
    });

    const s = repo.insert({ symbol: 'AAPL', features: { rsi: 45 }, tradeId: trade.id, sampledAt: now() });
    const byTrade = repo.getByTradeId(trade.id);
    expect(byTrade.length).toBe(1);
    expect(byTrade[0].id).toBe(s.id);
    db.close();
  });

  it('getByTradeId returns multiple samples in chronological order', () => {
    const { db, orderRepo, tradeRepo, repo } = setup();
    const order = orderRepo.create({
      symbol: 'AAPL', side: 'buy', orderType: 'market', quantity: 10, status: 'filled',
    });
    const trade = tradeRepo.create({
      symbol: 'AAPL', entryOrderId: order.id, entryPrice: 150, quantity: 10, fees: 0, status: 'open',
    });
    const t = now();
    repo.insert({ symbol: 'AAPL', features: { rsi: 30 }, tradeId: trade.id, sampledAt: t });
    repo.insert({ symbol: 'AAPL', features: { rsi: 35 }, tradeId: trade.id, sampledAt: t + 1 });

    const samples = repo.getByTradeId(trade.id);
    expect(samples.length).toBe(2);
    expect(samples[0].sampledAt).toBeLessThanOrEqual(samples[1].sampledAt);
    db.close();
  });

  it('getById returns null for missing id', () => {
    const { db, repo } = setup();
    expect(repo.getById(9999)).toBeNull();
    db.close();
  });
});
