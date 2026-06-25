export interface TickerProfitStats {
  symbol: string;
  cumulativePnl: number;
  tradeCount: number;
  winCount: number;
  winRate: number;  // derived: winCount / tradeCount, 0 when tradeCount = 0
  updatedAt: number;
}
