export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop';
export type OrderStatus = 'pending' | 'open' | 'filled' | 'partial' | 'cancelled' | 'rejected';

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  limitPrice?: number | null;
  stopPrice?: number | null;
  filledPrice?: number | null;
  filledQuantity?: number | null;
  status: OrderStatus;
  brokerOrderId?: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface OrderStatusEvent {
  id?: number;
  orderId: string;
  status: OrderStatus;
  filledPrice?: number | null;
  filledQuantity?: number | null;
  message?: string | null;
  occurredAt: number;
}
