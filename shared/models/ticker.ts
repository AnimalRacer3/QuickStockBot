export type TickerStateValue = 'watching' | 'holding' | 'idle';

export interface ActiveTicker {
  symbol: string;
  price: number;
  volume: number;
  rsi?: number | null;
  macd?: number | null;
  signal?: number | null;
  emaShort?: number | null;
  emaLong?: number | null;
  state: TickerStateValue;
  updatedAt: number;
}
