import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';
import { Trade, TradeLabel } from '../../../shared/models';

interface TradeRow {
  id: string;
  symbol: string;
  entry_order_id: string;
  exit_order_id: string | null;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  gross_pnl: number | null;
  net_pnl: number | null;
  fees: number;
  label: string | null;
  status: string;
  opened_at: number;
  closed_at: number | null;
}

export class TradeRepository {
  constructor(private db: Database.Database) {}

  private toModel(row: TradeRow): Trade {
    return {
      id: row.id,
      symbol: row.symbol,
      entryOrderId: row.entry_order_id,
      exitOrderId: row.exit_order_id,
      entryPrice: row.entry_price,
      exitPrice: row.exit_price,
      quantity: row.quantity,
      grossPnl: row.gross_pnl,
      netPnl: row.net_pnl,
      fees: row.fees,
      label: row.label as TradeLabel | null,
      status: row.status as Trade['status'],
      openedAt: row.opened_at,
      closedAt: row.closed_at,
    };
  }

  create(trade: Omit<Trade, 'id' | 'openedAt'>): Trade {
    const id = randomUUID();
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `INSERT INTO trades
           (id, symbol, entry_order_id, exit_order_id, entry_price, exit_price,
            quantity, gross_pnl, net_pnl, fees, label, status, opened_at, closed_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id, trade.symbol, trade.entryOrderId, trade.exitOrderId ?? null,
        trade.entryPrice, trade.exitPrice ?? null, trade.quantity,
        trade.grossPnl ?? null, trade.netPnl ?? null, trade.fees,
        trade.label ?? null, trade.status, now, trade.closedAt ?? null,
      );
    return { ...trade, id, openedAt: now };
  }

  getById(id: string): Trade | null {
    const row = this.db
      .prepare('SELECT * FROM trades WHERE id = ?')
      .get(id) as TradeRow | undefined;
    return row ? this.toModel(row) : null;
  }

  getOpenTrades(): Trade[] {
    const rows = this.db
      .prepare("SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at DESC")
      .all() as TradeRow[];
    return rows.map((r) => this.toModel(r));
  }

  close(
    id: string,
    exitOrderId: string,
    exitPrice: number,
    grossPnl: number,
    netPnl: number,
    fees: number,
  ): Trade {
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `UPDATE trades
         SET exit_order_id = ?, exit_price = ?, gross_pnl = ?,
             net_pnl = ?, fees = ?, status = 'closed', closed_at = ?
         WHERE id = ?`,
      )
      .run(exitOrderId, exitPrice, grossPnl, netPnl, fees, now, id);
    const trade = this.getById(id);
    if (!trade) throw new Error(`Trade not found: ${id}`);
    return trade;
  }

  setLabel(id: string, label: TradeLabel): Trade {
    this.db.prepare('UPDATE trades SET label = ? WHERE id = ?').run(label, id);
    const trade = this.getById(id);
    if (!trade) throw new Error(`Trade not found: ${id}`);
    return trade;
  }

  getByEntryOrderId(orderId: string): Trade | null {
    const row = this.db
      .prepare('SELECT * FROM trades WHERE entry_order_id = ?')
      .get(orderId) as TradeRow | undefined;
    return row ? this.toModel(row) : null;
  }

  getByExitOrderId(orderId: string): Trade | null {
    const row = this.db
      .prepare('SELECT * FROM trades WHERE exit_order_id = ?')
      .get(orderId) as TradeRow | undefined;
    return row ? this.toModel(row) : null;
  }
}
