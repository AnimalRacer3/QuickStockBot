/**
 * Mock relay WebSocket server for Playwright e2e tests.
 * Implements the web↔relay protocol with canned fixture data.
 */
import { WebSocketServer, WebSocket } from "ws";
import type { BotSettings } from "../src/lib/types";

const PORT = 9797;
const PASSWORD = "testpassword";

const MOCK_SETTINGS: BotSettings = {
  bot_id: "test-bot-001",
  pre_open_lead_hours: 1.0,
  scan_duration_hours: 3.0,
  scanner_refresh_seconds: 60,
  relative_volume_min: 2.0,
  gap_up_min_pct: 5.0,
  max_float_shares: 20_000_000,
  include_unknown_float: true,
  require_news: true,
  active_tickers_n: 3,
  prior_profit_bias_weight: 0.5,
  enabled_patterns: ["bullish_engulfing", "hammer", "morning_star"],
  pattern_candle_lookback: 5,
  macd_fast: 12,
  macd_slow: 26,
  macd_signal: 9,
  macd_slope_lookback: 3,
  macd_enforce_above_zero: true,
  risk_per_trade_pct: 1.0,
  daily_max_loss_pct: 3.0,
  daily_profit_target_pct: 5.0,
  override_risk_per_trade: false,
  flatten_on_daily_loss: true,
  flatten_on_daily_profit: false,
  daily_target_mode: "giveback",
  daily_giveback_pct: 25.0,
  exit_mode: "dump",
  stop_loss_pct: 2.0,
  take_profit_pct: 4.0,
  trailing_stop_enabled: false,
  force_close_at_close: true,
};

let liveSettings = { ...MOCK_SETTINGS };

const MOCK_TICKERS = [
  {
    symbol: "AAPL",
    last_price: 15.5,
    high_of_day: 16.2,
    low_of_day: 14.8,
    macd_line: 0.12,
    macd_signal_line: 0.08,
    macd_hist: 0.04,
    pattern_tags: ["hammer"],
    score: 72,
    updated_at: new Date().toISOString(),
    rvol: 3.2,
    pct_change: 4.5,
    float_shares: 8_500_000,
    unknown_float: false,
    tradable: true,
    role: "leader",
    gap_pct: 4.5,
  },
  {
    symbol: "MEME",
    last_price: 8.2,
    high_of_day: 8.9,
    low_of_day: 7.5,
    macd_line: 0.05,
    macd_signal_line: 0.03,
    macd_hist: 0.02,
    pattern_tags: [],
    score: 58,
    updated_at: new Date().toISOString(),
    rvol: 5.8,
    pct_change: 12.3,
    float_shares: undefined,
    unknown_float: true,
    tradable: false,
    role: "laggard",
    gap_pct: 12.3,
  },
];

const MOCK_TRADES = [
  {
    id: "trade-001",
    symbol: "AAPL",
    type: "buy",
    timestamp: "2024-03-05T09:35:22Z",
    qty: 100,
    price: 15.2,
    net_pl: 45.0,
    status: "filled",
    label: "good",
    opened_at: "2024-03-05T09:35:22Z",
    closed_at: "2024-03-05T10:05:00Z",
    entry_order: { id: "ord-001", type: "buy", qty: 100, submitted_price: 15.2, filled_price: 15.2, status: "filled", submitted_at: "2024-03-05T09:35:22Z" },
    exit_order: { id: "ord-002", type: "sell", qty: 100, submitted_price: 15.65, filled_price: 15.65, status: "filled", submitted_at: "2024-03-05T10:05:00Z" },
    status_history: [
      { status: "pending", timestamp: "2024-03-05T09:35:22Z" },
      { status: "filled", timestamp: "2024-03-05T09:35:23Z", filled_qty: 100, filled_price: 15.2 },
    ],
  },
  {
    id: "trade-002",
    symbol: "MEME",
    type: "buy",
    timestamp: "2024-03-12T09:40:11Z",
    qty: 200,
    price: 8.5,
    net_pl: -80.0,
    status: "filled",
    label: "bad",
    opened_at: "2024-03-12T09:40:11Z",
    closed_at: "2024-03-12T10:15:00Z",
    entry_order: { id: "ord-003", type: "buy", qty: 200, submitted_price: 8.5, filled_price: 8.5, status: "filled", submitted_at: "2024-03-12T09:40:11Z" },
    exit_order: { id: "ord-004", type: "sell", qty: 200, submitted_price: 8.1, filled_price: 8.1, status: "filled", submitted_at: "2024-03-12T10:15:00Z" },
    status_history: [
      { status: "pending", timestamp: "2024-03-12T09:40:11Z" },
      { status: "filled", timestamp: "2024-03-12T09:40:12Z", filled_qty: 200, filled_price: 8.5 },
    ],
  },
  {
    // Trail-off exit: AAPL entry scaled out across 3 candles then daily halt fired
    id: "trade-003",
    symbol: "AAPL",
    type: "buy",
    timestamp: "2024-03-05T09:36:00Z",
    qty: 100,
    price: 15.0,
    net_pl: 75.0,
    status: "filled",
    label: "good",
    opened_at: "2024-03-05T09:36:00Z",
    closed_at: "2024-03-05T10:30:00Z",
    entry_order: { id: "ord-007", type: "buy", qty: 100, submitted_price: 15.0, filled_price: 15.0, status: "filled", submitted_at: "2024-03-05T09:36:00Z" },
    exit_order: { id: "ord-011", type: "sell", qty: 50, submitted_price: 16.5, filled_price: 16.5, status: "filled", submitted_at: "2024-03-05T10:30:00Z" },
    status_history: [
      { status: "pending", timestamp: "2024-03-05T09:36:00Z" },
      { status: "filled", timestamp: "2024-03-05T09:36:01Z", filled_qty: 100, filled_price: 15.0 },
      { status: "partial_exit", timestamp: "2024-03-05T09:41:00Z", filled_qty: 25, filled_price: 15.6 },
      { status: "partial_exit", timestamp: "2024-03-05T09:46:00Z", filled_qty: 25, filled_price: 16.0 },
      { status: "exited", timestamp: "2024-03-05T10:30:00Z", filled_qty: 50, filled_price: 16.5 },
    ],
  },
];

const MOCK_DAILY_PL = [
  // March 5: trade-001 ($45) + trade-003 trail-off ($75) = $120 profit, 2 trades → green
  { date: "2024-03-05", total_pl: 120.0, trade_count: 2 },
  { date: "2024-03-12", total_pl: -80.0, trade_count: 1 },
  { date: "2024-03-19", total_pl: 0, trade_count: 1 },
];

function send(ws: WebSocket, msg: object) {
  ws.send(JSON.stringify(msg));
}

function handleRpc(ws: WebSocket, id: string, method: string, params: Record<string, unknown>) {
  switch (method) {
    case "get_state":
      send(ws, { type: "rpc_response", id, payload: { result: { tickers: MOCK_TICKERS, account: { buying_power: 25000, equity: 50000, pdt_flag: false, open_positions: 0, snapshot_at: new Date().toISOString() } } } });
      break;
    case "get_active_tickers":
      send(ws, { type: "rpc_response", id, payload: { result: { symbols: MOCK_TICKERS.map((t) => t.symbol) } } });
      break;
    case "get_ticker_detail": {
      const sym = params.symbol as string;
      const ticker = MOCK_TICKERS.find((t) => t.symbol === sym);
      if (ticker) {
        send(ws, { type: "rpc_response", id, payload: { result: ticker } });
      } else {
        send(ws, { type: "rpc_response", id, payload: { result: null, error: { code: "NOT_FOUND", message: "Ticker not found" } } });
      }
      break;
    }
    case "get_settings":
      send(ws, { type: "rpc_response", id, payload: { result: liveSettings } });
      break;
    case "update_settings": {
      const patch = params.patch as Partial<BotSettings>;
      liveSettings = { ...liveSettings, ...patch };
      send(ws, { type: "rpc_response", id, payload: { result: liveSettings } });
      break;
    }
    case "get_lists":
      send(ws, { type: "rpc_response", id, payload: { result: { watchlist: ["AAPL", "NVDA"], blacklist: ["GME"] } } });
      break;
    case "update_lists":
      send(ws, { type: "rpc_response", id, payload: { result: { watchlist: params.watchlist ?? [], blacklist: params.blacklist ?? [] } } });
      break;
    case "get_trade_history":
      send(ws, { type: "rpc_response", id, payload: { result: { trades: MOCK_TRADES, total: MOCK_TRADES.length } } });
      break;
    case "get_daily_pl": {
      const { year, month } = params as { year: number; month: number };
      const filtered = MOCK_DAILY_PL.filter((d) => {
        const [y, m] = d.date.split("-").map(Number);
        return y === year && m === month;
      });
      send(ws, { type: "rpc_response", id, payload: { result: { days: filtered } } });
      break;
    }
    case "subscribe_logs":
      send(ws, { type: "rpc_response", id, payload: { result: { subscribed: true } } });
      setTimeout(() => {
        send(ws, {
          type: "log",
          id: randomId(),
          payload: { timestamp: new Date().toISOString(), category: "system", message: "Mock relay connected — scanner idle" },
        });
      }, 200);
      break;
    default:
      send(ws, { type: "rpc_response", id, payload: { result: null, error: { code: "UNKNOWN_METHOD", message: `Unknown method: ${method}` } } });
  }
}

function randomId(): string {
  return Math.random().toString(36).slice(2);
}

export function startMockRelay(): WebSocketServer {
  // Reset settings for each test run
  liveSettings = { ...MOCK_SETTINGS };

  const wss = new WebSocketServer({ port: PORT });

  wss.on("connection", (ws) => {
    const nonce = randomId();
    send(ws, { type: "auth_challenge", id: randomId(), payload: { nonce } });

    ws.on("message", (raw) => {
      let msg: { type: string; id: string; payload: Record<string, unknown> };
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        return;
      }

      switch (msg.type) {
        case "web_auth": {
          const pw = msg.payload.password as string;
          if (pw === PASSWORD) {
            send(ws, { type: "auth_ok", id: msg.id, payload: {} });
            // Push initial state update
            setTimeout(() => {
              send(ws, {
                type: "state_update",
                id: randomId(),
                payload: {
                  tickers: MOCK_TICKERS,
                  account: {
                    buying_power: 25000,
                    equity: 50000,
                    pdt_flag: false,
                    open_positions: 0,
                    snapshot_at: new Date().toISOString(),
                  },
                },
              });
            }, 100);
            // Pipeline simulation: scanner → entry → trail-off exits → daily halt
            const pipelineLogs = [
              { delay: 300, category: "system", message: "scanner idle: pre-open window not yet reached" },
              { delay: 500, category: "info", message: "Scanner pass complete: 2 candidates, active=[AAPL] (MEME: unknown float, tradable=false)" },
              { delay: 700, category: "trade", message: "ENTRY AAPL: 100 shares @ 15.00 (front-side momentum, score=72, gate=all gates passed)" },
              { delay: 900, category: "trade", message: "PARTIAL EXIT AAPL: sold 25 of 100 shares @ 15.60 (trail_off per_candle scale-out)" },
              { delay: 1100, category: "trade", message: "PARTIAL EXIT AAPL: sold 25 of 75 shares @ 16.00 (trail_off per_candle scale-out)" },
              { delay: 1300, category: "trade", message: "EXIT AAPL: sold 50 shares @ 16.50 (bullishness ended, dumping remainder), pnl=$75.00" },
              { delay: 1500, category: "system", message: "HALT: daily profit target hit (5.20% >= 5.00%) — no new entries for remainder of session" },
            ];
            for (const { delay, category, message } of pipelineLogs) {
              setTimeout(() => {
                send(ws, {
                  type: "log",
                  id: randomId(),
                  payload: { timestamp: new Date().toISOString(), category, message },
                });
              }, delay);
            }
          } else {
            send(ws, { type: "auth_failed", id: msg.id, payload: { message: "Invalid password" } });
          }
          break;
        }
        case "rpc_request": {
          const { method, params } = msg.payload as { method: string; params: Record<string, unknown> };
          handleRpc(ws, msg.id, method, params ?? {});
          break;
        }
      }
    });
  });

  return wss;
}

export const RELAY_URL = `ws://localhost:${PORT}`;
export const RELAY_PASSWORD = PASSWORD;

// When run directly as a script, start the server
if (process.argv[1] && process.argv[1].endsWith("mock-relay.ts")) {
  const wss = startMockRelay();
  console.log(`Mock relay listening on ws://localhost:${PORT}`);
  process.on("SIGINT", () => {
    wss.close();
    process.exit(0);
  });
}
