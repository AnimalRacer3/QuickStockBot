/**
 * Frozen TypeScript types generated from /shared/schemas/*.schema.json
 * Do not edit by hand — any changes must be reflected in the corresponding JSON Schema.
 */

// ─── Settings ────────────────────────────────────────────────────────────────

export type LogLevel = "debug" | "info" | "warning" | "error";
export type Broker = "alpaca";

export interface Settings {
  bot_id: string;
  relay_url: string;
  license_key: string;
  connection_password?: string;
  paper_trading?: boolean;
  broker?: Broker;
  broker_api_key?: string;
  broker_api_secret?: string;
  watchlist?: string[];
  blacklist?: string[];
  max_positions?: number;
  risk_per_trade_pct?: number;
  min_score?: number;
  auto_trade?: boolean;
  macd_fast?: number;
  macd_slow?: number;
  macd_signal?: number;
  log_level?: LogLevel;
}

// ─── TickerState ─────────────────────────────────────────────────────────────

export interface TickerState {
  symbol: string;
  last_price: number;
  high_of_day: number;
  low_of_day: number;
  macd_line: number;
  macd_signal: number;
  macd_hist: number;
  pattern_tags: string[];
  score: number;
  updated_at: string; // ISO-8601 UTC
}

// ─── Order ───────────────────────────────────────────────────────────────────

export type OrderType = "buy" | "sell" | "short" | "limit";
export type OrderStatus = "pending" | "filled" | "partial" | "cancelled" | "rejected";

export interface Order {
  id: string;
  type: OrderType;
  symbol: string;
  qty: number;
  submitted_price: number;
  status: OrderStatus;
  filled_qty?: number;
  filled_price?: number;
  submitted_at?: string;
  updated_at?: string;
}

// ─── OrderStatusEvent ─────────────────────────────────────────────────────────

export interface OrderStatusEvent {
  order_id: string;
  status: OrderStatus;
  /** UTC timestamp truncated to the second: YYYY-MM-DDTHH:MM:SSZ */
  timestamp: string;
  filled_qty?: number;
  filled_price?: number;
}

// ─── Trade ───────────────────────────────────────────────────────────────────

export type TradeLabel = "good" | "bad";

export interface Trade {
  id: string;
  symbol: string;
  entry_order: Order;
  exit_order: Order;
  net_pl: number;
  label: TradeLabel;
  opened_at?: string;
  closed_at?: string;
}

// ─── LogEvent ────────────────────────────────────────────────────────────────

export type LogCategory = "info" | "warning" | "error" | "trade" | "order" | "system";

export interface LogEvent {
  timestamp: string;
  category: LogCategory;
  message: string;
  payload?: Record<string, unknown>;
}

// ─── AccountSnapshot ─────────────────────────────────────────────────────────

export interface AccountSnapshot {
  buying_power: number;
  equity: number;
  pdt_flag: boolean;
  pdt_trades_remaining?: number;
  open_positions?: number;
  snapshot_at: string;
}

// ─── Relay Protocol ──────────────────────────────────────────────────────────

/** Every WebSocket frame is wrapped in this envelope. */
export interface Envelope<T extends string = string, P = unknown> {
  type: T;
  id: string; // UUID v4
  payload: P;
}

// Bot → Relay message types
export type BotToRelayMessageType =
  | "register"
  | "log"
  | "state_update"
  | "rpc_response";

export interface RegisterPayload {
  bot_id: string;
  license_key: string;
  connection_password_proof: string;
  version: string;
}

export interface StateUpdatePayload {
  tickers: TickerState[];
  account?: AccountSnapshot;
}

export interface RpcResponsePayload {
  result: unknown;
  error?: { code: string; message: string };
}

export type RegisterMessage = Envelope<"register", RegisterPayload>;
export type LogMessage = Envelope<"log", LogEvent>;
export type StateUpdateMessage = Envelope<"state_update", StateUpdatePayload>;
export type RpcResponseMessage = Envelope<"rpc_response", RpcResponsePayload>;

export type BotToRelayMessage =
  | RegisterMessage
  | LogMessage
  | StateUpdateMessage
  | RpcResponseMessage;

// Relay → Bot message types
export type RelayToBotMessageType = "auth_challenge" | "rpc_request";

export interface AuthChallengePayload {
  nonce: string;
}

export type RpcMethodName =
  | "get_state"
  | "get_active_tickers"
  | "get_ticker_detail"
  | "get_settings"
  | "update_settings"
  | "get_lists"
  | "update_lists"
  | "get_trade_history"
  | "get_order_detail"
  | "subscribe_logs";

export interface RpcRequestPayload {
  method: RpcMethodName;
  params?: Record<string, unknown>;
}

export type AuthChallengeMessage = Envelope<"auth_challenge", AuthChallengePayload>;
export type RpcRequestMessage = Envelope<"rpc_request", RpcRequestPayload>;

export type RelayToBotMessage = AuthChallengeMessage | RpcRequestMessage;

// Auth fields reference
export interface AuthFields {
  license_key: string;
  bot_id: string;
  connection_password_proof: string;
}
