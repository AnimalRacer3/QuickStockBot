import type { DailyPL, ExtendedTickerState, BotSettings, TradeDetail } from "./types";

export type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

export interface AccountSnapshot {
  buying_power: number;
  equity: number;
  pdt_flag: boolean;
  pdt_trades_remaining?: number;
  open_positions?: number;
  snapshot_at: string;
}

export interface LogEvent {
  timestamp: string;
  category: "info" | "warning" | "error" | "trade" | "order" | "system";
  message: string;
  payload?: Record<string, unknown>;
}

export interface StateUpdate {
  tickers: ExtendedTickerState[];
  account?: AccountSnapshot;
}

type LogListener = (event: LogEvent) => void;
type StateListener = (payload: StateUpdate) => void;
type StateChangeListener = (state: ConnectionState) => void;

function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export class RelayClient {
  private ws: WebSocket | null = null;
  private pending = new Map<
    string,
    { resolve: (r: unknown) => void; reject: (e: Error) => void }
  >();
  private logListeners = new Set<LogListener>();
  private stateListeners = new Set<StateListener>();
  private stateChangeListeners = new Set<StateChangeListener>();
  private _connectionState: ConnectionState = "disconnected";

  get connectionState(): ConnectionState {
    return this._connectionState;
  }

  private setConnectionState(s: ConnectionState) {
    this._connectionState = s;
    this.stateChangeListeners.forEach((l) => l(s));
  }

  connect(relayUrl: string, password: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.setConnectionState("connecting");
      // Normalize http(s):// → ws(s):// so users can paste either form
      const normalizedUrl = relayUrl
        .replace(/^https:\/\//i, "wss://")
        .replace(/^http:\/\//i, "ws://");
      let ws: WebSocket;
      try {
        ws = new WebSocket(normalizedUrl);
      } catch {
        this.setConnectionState("error");
        reject(new Error("Failed to create WebSocket"));
        return;
      }
      this.ws = ws;

      const timeout = setTimeout(() => {
        this.setConnectionState("error");
        ws.close();
        reject(new Error("Connection timeout"));
      }, 15000);

      ws.onmessage = (event) => {
        let msg: { type: string; id: string; payload: Record<string, unknown> };
        try {
          msg = JSON.parse(event.data as string);
        } catch {
          return;
        }

        switch (msg.type) {
          case "auth_challenge": {
            ws.send(
              JSON.stringify({
                type: "web_auth",
                id: msg.id,
                payload: { password },
              })
            );
            break;
          }
          case "auth_ok": {
            clearTimeout(timeout);
            this.setConnectionState("connected");
            resolve();
            break;
          }
          case "auth_failed": {
            clearTimeout(timeout);
            this.setConnectionState("error");
            ws.close();
            reject(new Error((msg.payload.message as string) ?? "Authentication failed"));
            break;
          }
          case "rpc_response": {
            const p = this.pending.get(msg.id);
            if (p) {
              this.pending.delete(msg.id);
              const payload = msg.payload as { result?: unknown; error?: { message: string } };
              if (payload.error) {
                p.reject(new Error(payload.error.message));
              } else {
                p.resolve(payload.result);
              }
            }
            break;
          }
          case "log": {
            const event = msg.payload as unknown as LogEvent;
            this.logListeners.forEach((l) => l(event));
            break;
          }
          case "state_update": {
            const payload = msg.payload as unknown as StateUpdate;
            this.stateListeners.forEach((l) => l(payload));
            break;
          }
        }
      };

      ws.onerror = () => {
        clearTimeout(timeout);
        this.setConnectionState("error");
        this.rejectAll("WebSocket error");
        reject(new Error("WebSocket connection error"));
      };

      ws.onclose = () => {
        clearTimeout(timeout);
        if (this._connectionState !== "error") {
          this.setConnectionState("disconnected");
        }
        this.rejectAll("Connection closed");
      };
    });
  }

  private rejectAll(reason: string) {
    for (const p of this.pending.values()) {
      p.reject(new Error(reason));
    }
    this.pending.clear();
  }

  async rpc<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected");
    }
    return new Promise((resolve, reject) => {
      const id = uuid();
      this.pending.set(id, { resolve: (r) => resolve(r as T), reject });
      this.ws!.send(
        JSON.stringify({
          type: "rpc_request",
          id,
          payload: { method, params: params ?? {} },
        })
      );
    });
  }

  async getSettings(): Promise<BotSettings> {
    return this.rpc<BotSettings>("get_settings");
  }

  async updateSettings(patch: Partial<BotSettings>): Promise<BotSettings> {
    return this.rpc<BotSettings>("update_settings", { patch });
  }

  async getState(): Promise<{ tickers: ExtendedTickerState[]; account?: AccountSnapshot }> {
    return this.rpc("get_state");
  }

  async getTickerDetail(symbol: string): Promise<ExtendedTickerState> {
    return this.rpc("get_ticker_detail", { symbol });
  }

  async getLists(): Promise<{ watchlist: string[]; blacklist: string[] }> {
    return this.rpc("get_lists");
  }

  async updateLists(
    watchlist: string[],
    blacklist: string[]
  ): Promise<{ watchlist: string[]; blacklist: string[] }> {
    return this.rpc("update_lists", { watchlist, blacklist });
  }

  async getTradeHistory(
    limit = 100,
    offset = 0
  ): Promise<{ trades: TradeDetail[]; total: number }> {
    return this.rpc("get_trade_history", { limit, offset });
  }

  async getDailyPL(year: number, month: number): Promise<{ days: DailyPL[] }> {
    return this.rpc("get_daily_pl", { year, month });
  }

  async subscribeLogs(): Promise<void> {
    await this.rpc("subscribe_logs", { categories: [], min_level: "info" });
  }

  onLog(cb: LogListener): () => void {
    this.logListeners.add(cb);
    return () => this.logListeners.delete(cb);
  }

  onStateUpdate(cb: StateListener): () => void {
    this.stateListeners.add(cb);
    return () => this.stateListeners.delete(cb);
  }

  onConnectionStateChange(cb: StateChangeListener): () => void {
    this.stateChangeListeners.add(cb);
    return () => this.stateChangeListeners.delete(cb);
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
    this.setConnectionState("disconnected");
  }
}
