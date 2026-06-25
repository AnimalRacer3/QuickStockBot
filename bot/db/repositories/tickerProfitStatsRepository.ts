import Database from 'better-sqlite3';
import { TickerProfitStats } from '../../../shared/models';

interface TickerProfitStatsRow {
  symbol: string;
  cumulative_pnl: number;
  trade_count: number;
  win_count: number;
  updated_at: number;
}

export class TickerProfitStatsRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: TickerProfitStatsRow): TickerProfitStats {
    return {
      symbol: row.symbol,
      cumulativePnl: row.cumulative_pnl,
      tradeCount: row.trade_count,
      winCount: row.win_count,
      winRate: row.trade_count > 0 ? row.win_count / row.trade_count : 0,
      updatedAt: row.updated_at,
    };
  }

  getBySymbol(symbol: string): TickerProfitStats | null {
    const row = this.db
      .prepare('SELECT * FROM ticker_profit_stats WHERE symbol = ?')
      .get(symbol) as TickerProfitStatsRow | undefined;
    return row ? this.toModel(row) : null;
  }

  getAll(): TickerProfitStats[] {
    const rows = this.db
      .prepare('SELECT * FROM ticker_profit_stats ORDER BY cumulative_pnl DESC')
      .all() as TickerProfitStatsRow[];
    return rows.map((r) => this.toModel(r));
  }

  /** Record a completed round-trip: upsert cumulative stats for the symbol. */
  recordTrade(symbol: string, netPnl: number): TickerProfitStats {
    const now = Math.floor(Date.now() / 1000);
    const isWin = netPnl > 0 ? 1 : 0;

    this.db
      .prepare(
        `INSERT INTO ticker_profit_stats
           (symbol, cumulative_pnl, trade_count, win_count, updated_at)
         VALUES (?, ?, 1, ?, ?)
         ON CONFLICT(symbol) DO UPDATE SET
           cumulative_pnl = cumulative_pnl + excluded.cumulative_pnl,
           trade_count    = trade_count + 1,
           win_count      = win_count + excluded.win_count,
           updated_at     = excluded.updated_at`,
      )
      .run(symbol, netPnl, isWin, now);

    return this.getBySymbol(symbol)!;
  }

  /** Reset stats for a symbol (e.g. start of new evaluation period). */
  reset(symbol: string): void {
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `INSERT INTO ticker_profit_stats
           (symbol, cumulative_pnl, trade_count, win_count, updated_at)
         VALUES (?, 0, 0, 0, ?)
         ON CONFLICT(symbol) DO UPDATE SET
           cumulative_pnl = 0, trade_count = 0, win_count = 0, updated_at = excluded.updated_at`,
      )
      .run(symbol, now);
  }
}
