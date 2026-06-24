export type TradeLabel = 'good' | 'bad';
export type TradeStatus = 'open' | 'closed';

export interface Trade {
  id: string;
  symbol: string;
  entryOrderId: string;
  exitOrderId?: string | null;
  entryPrice: number;
  exitPrice?: number | null;
  quantity: number;
  grossPnl?: number | null;
  netPnl?: number | null;
  fees: number;
  label?: TradeLabel | null;
  status: TradeStatus;
  openedAt: number;
  closedAt?: number | null;
}
