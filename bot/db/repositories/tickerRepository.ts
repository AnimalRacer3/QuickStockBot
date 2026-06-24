import Database from 'better-sqlite3';
import { ActiveTicker } from '../../../shared/models';

interface TickerRow {
  symbol: string;
  price: number;
  volume: number;
  rsi: number | null;
  macd: number | null;
  signal: number | null;
  ema_short: number | null;
  ema_long: number | null;
  state: string;
  updated_at: number;
}

export class TickerRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: TickerRow): ActiveTicker {
    return {
      symbol: row.symbol,
      price: row.price,
      volume: row.volume,
      rsi: row.rsi,
      macd: row.macd,
      signal: row.signal,
      emaShort: row.ema_short,
      emaLong: row.ema_long,
      state: row.state as ActiveTicker['state'],
      updatedAt: row.updated_at,
    };
  }

  upsert(ticker: ActiveTicker): ActiveTicker {
    const now = Math.floor(Date.now() / 1000);
    const saved = { ...ticker, updatedAt: now };
    this.db
      .prepare(
        `INSERT INTO active_tickers
           (symbol, price, volume, rsi, macd, signal, ema_short, ema_long, state, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(symbol) DO UPDATE SET
           price = excluded.price, volume = excluded.volume,
           rsi = excluded.rsi, macd = excluded.macd, signal = excluded.signal,
           ema_short = excluded.ema_short, ema_long = excluded.ema_long,
           state = excluded.state, updated_at = excluded.updated_at`,
      )
      .run(
        saved.symbol, saved.price, saved.volume,
        saved.rsi ?? null, saved.macd ?? null, saved.signal ?? null,
        saved.emaShort ?? null, saved.emaLong ?? null,
        saved.state, saved.updatedAt,
      );
    return saved;
  }

  getBySymbol(symbol: string): ActiveTicker | null {
    const row = this.db
      .prepare('SELECT * FROM active_tickers WHERE symbol = ?')
      .get(symbol) as TickerRow | undefined;
    return row ? this.toModel(row) : null;
  }

  getAll(): ActiveTicker[] {
    const rows = this.db
      .prepare('SELECT * FROM active_tickers ORDER BY symbol')
      .all() as TickerRow[];
    return rows.map((r) => this.toModel(r));
  }

  delete(symbol: string): void {
    this.db.prepare('DELETE FROM active_tickers WHERE symbol = ?').run(symbol);
  }
}
