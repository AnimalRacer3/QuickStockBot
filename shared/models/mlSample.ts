export interface MlSample {
  id?: number;
  symbol: string;
  features: Record<string, number>;
  label?: number | null;
  modelVersion?: string | null;
  tradeId?: string | null;
  sampledAt: number;
}
