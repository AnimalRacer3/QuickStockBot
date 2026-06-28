import type { WebSocket } from "ws";

// ─── Protocol types (mirrors shared/types/index.ts — relay is standalone) ─────

export interface Envelope<T extends string = string, P = unknown> {
  type: T;
  id: string;
  payload: P;
}

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

export interface LogEvent {
  timestamp: string;
  category: string;
  message: string;
  payload?: Record<string, unknown>;
}

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
  updated_at: string;
}

export interface AccountSnapshot {
  buying_power: number;
  equity: number;
  pdt_flag: boolean;
  pdt_trades_remaining?: number;
  open_positions?: number;
  snapshot_at: string;
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

// ─── Bot connection record ────────────────────────────────────────────────────

export interface BotRecord {
  ws: WebSocket;
  bot_id: string;
  account_id: string;
  /** Raw connection password stored so web clients can auth against it */
  connection_password?: string;
  version: string;
  registered_at: number;
  last_ping_at: number;
}

// ─── Web client record ────────────────────────────────────────────────────────

export interface WebClientRecord {
  ws: WebSocket;
  account_id: string;
  /** Bot this web client authenticated against; used as fallback bot_id in RPCs */
  default_bot_id?: string;
  connected_at: number;
  last_ping_at: number;
}

// ─── Pending RPC calls ────────────────────────────────────────────────────────

export interface PendingRpc {
  resolve: (payload: unknown) => void;
  reject: (err: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
}

// ─── Web ↔ Relay wire types ──────────────────────────────────────────────────

export interface WebRpcRequestPayload {
  /** Optional when the web client authenticated via /ws/<bot_id> — relay uses the auth bot as default */
  bot_id?: string;
  method: RpcMethodName;
  params?: Record<string, unknown>;
}

export interface WebRpcResponsePayload {
  result?: unknown;
  error?: { code: string; message: string };
}

export interface WebStateUpdatePayload {
  bot_id: string;
  tickers: TickerState[];
  account?: AccountSnapshot;
}

export interface WebLogPayload {
  bot_id: string;
  event: LogEvent;
}

export type WebToRelayMessage = {
  type: "rpc_request";
  id: string;
  payload: WebRpcRequestPayload;
};

export type RelayToWebMessage =
  | { type: "rpc_response"; id: string; payload: WebRpcResponsePayload }
  | { type: "state_update"; id: string; payload: WebStateUpdatePayload }
  | { type: "log"; id: string; payload: WebLogPayload }
  | { type: "error"; id: string; payload: { code: string; message: string } };

// ─── License validation response ─────────────────────────────────────────────

export interface LicenseValidationResult {
  valid: boolean;
  account_id?: string;
  error?: string;
  /** Per-user connection password stored on the SaaS; used instead of the global RELAY_CONNECTION_SECRET. */
  connection_password?: string | null;
}
