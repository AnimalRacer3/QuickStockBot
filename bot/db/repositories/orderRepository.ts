import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';
import { Order, OrderStatus, OrderStatusEvent } from '../../../shared/models';

interface OrderRow {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price: number | null;
  stop_price: number | null;
  filled_price: number | null;
  filled_quantity: number | null;
  status: string;
  broker_order_id: string | null;
  created_at: number;
  updated_at: number;
}

interface EventRow {
  id: number;
  order_id: string;
  status: string;
  filled_price: number | null;
  filled_quantity: number | null;
  message: string | null;
  occurred_at: number;
}

export class OrderRepository {
  constructor(private db: Database.Database) {}

  private toOrder(row: OrderRow): Order {
    return {
      id: row.id,
      symbol: row.symbol,
      side: row.side as Order['side'],
      orderType: row.order_type as Order['orderType'],
      quantity: row.quantity,
      limitPrice: row.limit_price,
      stopPrice: row.stop_price,
      filledPrice: row.filled_price,
      filledQuantity: row.filled_quantity,
      status: row.status as OrderStatus,
      brokerOrderId: row.broker_order_id,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }

  private toEvent(row: EventRow): OrderStatusEvent {
    return {
      id: row.id,
      orderId: row.order_id,
      status: row.status as OrderStatus,
      filledPrice: row.filled_price,
      filledQuantity: row.filled_quantity,
      message: row.message,
      occurredAt: row.occurred_at,
    };
  }

  create(order: Omit<Order, 'id' | 'createdAt' | 'updatedAt'>): Order {
    const id = randomUUID();
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `INSERT INTO orders
           (id, symbol, side, order_type, quantity, limit_price, stop_price,
            filled_price, filled_quantity, status, broker_order_id, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id, order.symbol, order.side, order.orderType, order.quantity,
        order.limitPrice ?? null, order.stopPrice ?? null,
        order.filledPrice ?? null, order.filledQuantity ?? null,
        order.status, order.brokerOrderId ?? null, now, now,
      );
    this.addStatusEvent({ orderId: id, status: order.status, occurredAt: now });
    return { ...order, id, createdAt: now, updatedAt: now };
  }

  getById(id: string): Order | null {
    const row = this.db
      .prepare('SELECT * FROM orders WHERE id = ?')
      .get(id) as OrderRow | undefined;
    return row ? this.toOrder(row) : null;
  }

  getBySymbol(symbol: string): Order[] {
    const rows = this.db
      .prepare('SELECT * FROM orders WHERE symbol = ? ORDER BY created_at DESC')
      .all(symbol) as OrderRow[];
    return rows.map((r) => this.toOrder(r));
  }

  updateStatus(
    id: string,
    status: OrderStatus,
    filledPrice?: number,
    filledQuantity?: number,
  ): Order {
    const now = Math.floor(Date.now() / 1000);
    this.db
      .prepare(
        `UPDATE orders
         SET status = ?,
             filled_price    = COALESCE(?, filled_price),
             filled_quantity = COALESCE(?, filled_quantity),
             updated_at = ?
         WHERE id = ?`,
      )
      .run(status, filledPrice ?? null, filledQuantity ?? null, now, id);
    this.addStatusEvent({
      orderId: id,
      status,
      filledPrice: filledPrice ?? null,
      filledQuantity: filledQuantity ?? null,
      occurredAt: now,
    });
    const order = this.getById(id);
    if (!order) throw new Error(`Order not found: ${id}`);
    return order;
  }

  addStatusEvent(event: Omit<OrderStatusEvent, 'id'>): OrderStatusEvent {
    const occurredAt = event.occurredAt ?? Math.floor(Date.now() / 1000);
    const result = this.db
      .prepare(
        `INSERT INTO order_status_events
           (order_id, status, filled_price, filled_quantity, message, occurred_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(
        event.orderId, event.status,
        event.filledPrice ?? null, event.filledQuantity ?? null,
        event.message ?? null, occurredAt,
      );
    return { ...event, id: result.lastInsertRowid as number, occurredAt };
  }

  getStatusHistory(orderId: string): OrderStatusEvent[] {
    const rows = this.db
      .prepare(
        `SELECT * FROM order_status_events
         WHERE order_id = ?
         ORDER BY occurred_at ASC, id ASC`,
      )
      .all(orderId) as EventRow[];
    return rows.map((r) => this.toEvent(r));
  }
}
