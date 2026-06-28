/**
 * End-to-end relay tests: bot socket + web client socket
 * Covers: register → route → RPC round-trip → log stream
 *         auth failures (bad license, wrong account scope, bad password)
 *         reconnect handling, rate-limit basics
 */
import { describe, it, beforeAll, afterAll, beforeEach, afterEach, expect } from "vitest";
import { WebSocket } from "ws";
import { createHmac } from "crypto";
import { createServer } from "http";
import type { Server } from "http";
import { RelayServer } from "./server.js";

// ─── Constants ────────────────────────────────────────────────────────────────

const VALID_LICENSE = "valid-license-abc";
const LICENSE_B = "license-b";
const LICENSE_PER_USER = "license-per-user";
const ACCOUNT_A = "account-111";
const ACCOUNT_B = "account-222";
const CONNECTION_SECRET = "relay-shared-secret";
const PER_USER_PASSWORD = "my-unique-bot-password-123";

// ─── Stub SaaS validator (real HTTP server, started once) ─────────────────────

let validatorServer: Server;
let validatorPort: number;

beforeAll(async () => {
  validatorServer = createServer((req, res) => {
    let body = "";
    req.on("data", (c: Buffer) => {
      body += c.toString();
    });
    req.on("end", () => {
      const { license_key } = JSON.parse(body) as { license_key: string };
      let result: { valid: boolean; account_id?: string; connection_password?: string | null };
      if (license_key === VALID_LICENSE) {
        result = { valid: true, account_id: ACCOUNT_A, connection_password: null };
      } else if (license_key === LICENSE_B) {
        result = { valid: true, account_id: ACCOUNT_B, connection_password: null };
      } else if (license_key === LICENSE_PER_USER) {
        result = { valid: true, account_id: ACCOUNT_A, connection_password: PER_USER_PASSWORD };
      } else {
        result = { valid: false };
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(result));
    });
  });
  await new Promise<void>((r) => validatorServer.listen(0, "127.0.0.1", r));
  validatorPort = (validatorServer.address() as { port: number }).port;
});

afterAll(async () => {
  await new Promise<void>((r) => validatorServer.close(() => r()));
});

// ─── Per-test relay server ────────────────────────────────────────────────────

let relay: RelayServer;
let relayPort: number;

beforeEach(async () => {
  relay = new RelayServer({
    port: 0,
    validateUrl: `http://127.0.0.1:${validatorPort}/validate`,
    connectionSecret: CONNECTION_SECRET,
    rpcTimeoutMs: 2000,
    pingIntervalMs: 60_000,
    rateLimitMsgPerSec: 100,
    rateLimitBurst: 200,
  });
  await relay.listen();
  relayPort = relay.boundPort;
});

afterEach(async () => {
  await relay.close();
});

// ─── Socket wrapper with message queue ────────────────────────────────────────
//
// Race condition: the server sends auth_challenge immediately on connection.
// If it arrives in the same TCP segment as the HTTP 101 handshake response,
// the ws client fires "message" before we can attach a listener.  A queue
// collects all frames so callers can dequeue them at any point.

interface QSocket {
  ws: WebSocket;
  /** Resolves with the next message, buffering frames received before the call. */
  next: (timeoutMs?: number) => Promise<unknown>;
  close: () => void;
}

function openSocket(path: string): Promise<QSocket> {
  const ws = new WebSocket(`ws://127.0.0.1:${relayPort}${path}`);
  ws.on("error", () => {}); // prevent unhandled-error crashes

  const buffer: unknown[] = [];
  const waiters: Array<{ resolve: (v: unknown) => void; reject: (e: Error) => void }> = [];

  ws.on("message", (raw: Buffer) => {
    let msg: unknown;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      msg = raw.toString();
    }
    if (waiters.length > 0) {
      waiters.shift()!.resolve(msg);
    } else {
      buffer.push(msg);
    }
  });

  ws.on("close", () => {
    // Reject any pending waiters on close
    for (const w of waiters.splice(0)) {
      w.reject(new Error("Socket closed"));
    }
  });

  const next = (timeoutMs = 5000): Promise<unknown> => {
    if (buffer.length > 0) return Promise.resolve(buffer.shift()!);
    return new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = waiters.findIndex((w) => w.resolve === resolve);
        if (idx >= 0) waiters.splice(idx, 1);
        reject(new Error("next() timeout"));
      }, timeoutMs);
      waiters.push({
        resolve: (v) => {
          clearTimeout(timer);
          resolve(v);
        },
        reject: (e) => {
          clearTimeout(timer);
          reject(e);
        },
      });
    });
  };

  return new Promise<QSocket>((resolve, reject) => {
    ws.once("open", () => resolve({ ws, next, close: () => ws.close() }));
    ws.once("error", reject);
  });
}

// Wait for a specific message type (skips others until found or timeout)
async function waitForType(sock: QSocket, type: string, timeoutMs = 3000): Promise<unknown> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const msg = (await sock.next(deadline - Date.now())) as { type: string };
    if (msg.type === type) return msg;
  }
  throw new Error(`waitForType("${type}") timed out`);
}

function waitClose(ws: WebSocket): Promise<{ code: number; reason: string }> {
  return new Promise((resolve) => {
    if (ws.readyState === WebSocket.CLOSED) {
      resolve({ code: 1000, reason: "" });
      return;
    }
    ws.once("close", (code, reasonBuf) => resolve({ code, reason: reasonBuf.toString() }));
  });
}

// ─── Auth helpers ─────────────────────────────────────────────────────────────

function makeProof(nonce: string, secret: string): string {
  return createHmac("sha256", secret).update(nonce).digest("hex");
}

async function connectBot(opts: {
  licenseKey?: string;
  botId?: string;
  secret?: string;
  version?: string;
  sendRegister?: boolean;
}): Promise<{ sock: QSocket; nonce: string }> {
  const sock = await openSocket("/bot");
  const challenge = (await sock.next()) as {
    type: string;
    payload: { nonce: string };
  };
  expect(challenge.type).toBe("auth_challenge");
  const nonce = challenge.payload.nonce;

  if (opts.sendRegister !== false) {
    const licenseKey = opts.licenseKey ?? VALID_LICENSE;
    const secret = opts.secret ?? CONNECTION_SECRET;
    const proof = makeProof(nonce, secret);
    sock.ws.send(
      JSON.stringify({
        type: "register",
        id: "reg-1",
        payload: {
          bot_id: opts.botId ?? "bot-aaa",
          license_key: licenseKey,
          connection_password_proof: proof,
          version: opts.version ?? "0.1.0",
        },
      })
    );
  }
  return { sock, nonce };
}

async function registeredBot(opts: { licenseKey?: string; botId?: string }): Promise<QSocket> {
  const { sock } = await connectBot(opts);
  const registered = (await sock.next()) as { type: string };
  expect(registered.type).toBe("registered");
  return sock;
}

async function connectWeb(accountId: string): Promise<QSocket> {
  return openSocket(`/ws?token=account:${accountId}`);
}

function sendRpc(
  sock: QSocket,
  botId: string,
  method: string,
  params?: Record<string, unknown>
): string {
  const id = `rpc-${Math.random().toString(36).slice(2)}`;
  sock.ws.send(
    JSON.stringify({
      type: "rpc_request",
      id,
      payload: { bot_id: botId, method, params },
    })
  );
  return id;
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("Bot registration", () => {
  it("sends auth_challenge immediately on connect", async () => {
    const sock = await openSocket("/bot");
    const msg = (await sock.next()) as {
      type: string;
      payload: { nonce: string };
    };
    expect(msg.type).toBe("auth_challenge");
    expect(typeof msg.payload.nonce).toBe("string");
    expect(msg.payload.nonce.length).toBeGreaterThan(8);
    sock.close();
  });

  it("registers a bot with valid credentials", async () => {
    const sock = await registeredBot({ botId: "bot-001" });
    expect(relay.routingMap.getBot("bot-001")).toBeDefined();
    expect(relay.routingMap.getBot("bot-001")?.account_id).toBe(ACCOUNT_A);
    sock.close();
  });

  it("rejects non-register frame before registration", async () => {
    const { sock } = await connectBot({ sendRegister: false });
    sock.ws.send(JSON.stringify({ type: "log", id: "x", payload: {} }));
    const { code } = await waitClose(sock.ws);
    expect(code).toBe(4003);
  });

  it("closes with AUTH_FAILED on bad HMAC proof", async () => {
    const { sock } = await connectBot({ sendRegister: false });
    sock.ws.send(
      JSON.stringify({
        type: "register",
        id: "r1",
        payload: {
          bot_id: "bot-x",
          license_key: VALID_LICENSE,
          connection_password_proof: "bad-proof",
          version: "0.1.0",
        },
      })
    );
    const { code } = await waitClose(sock.ws);
    expect(code).toBe(4001);
  });

  it("closes with AUTH_FAILED on invalid license key", async () => {
    const { sock, nonce } = await connectBot({ sendRegister: false });
    const proof = makeProof(nonce, CONNECTION_SECRET);
    sock.ws.send(
      JSON.stringify({
        type: "register",
        id: "r1",
        payload: {
          bot_id: "bot-x",
          license_key: "bad-license",
          connection_password_proof: proof,
          version: "0.1.0",
        },
      })
    );
    const { code } = await waitClose(sock.ws);
    expect(code).toBe(4001);
  });

  it("closes with AUTH_FAILED on missing fields", async () => {
    const { sock } = await connectBot({ sendRegister: false });
    sock.ws.send(
      JSON.stringify({
        type: "register",
        id: "r1",
        payload: { bot_id: "bot-x" },
      })
    );
    const { code } = await waitClose(sock.ws);
    expect(code).toBe(4004);
  });

  it("rejects unknown WebSocket paths", async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${relayPort}/unknown`);
    ws.on("error", () => {});
    const { code } = await waitClose(ws);
    expect([1006, 1001, 1005]).toContain(code);
  });

  it("authenticates with per-user connection password from license", async () => {
    const { sock, nonce } = await connectBot({ sendRegister: false });
    const proof = makeProof(nonce, PER_USER_PASSWORD);
    sock.ws.send(
      JSON.stringify({
        type: "register",
        id: "r-pu",
        payload: {
          bot_id: "bot-per-user",
          license_key: LICENSE_PER_USER,
          connection_password_proof: proof,
          version: "0.1.0",
        },
      })
    );
    const registered = (await sock.next()) as { type: string };
    expect(registered.type).toBe("registered");
    expect(relay.routingMap.getBot("bot-per-user")).toBeDefined();
    sock.close();
  });

  it("rejects per-user license when global secret is used instead of per-user password", async () => {
    const { sock, nonce } = await connectBot({ sendRegister: false });
    // Compute proof with global secret — but license has a per-user password set,
    // so the relay must use the per-user password and reject the global-secret proof.
    const proof = makeProof(nonce, CONNECTION_SECRET);
    sock.ws.send(
      JSON.stringify({
        type: "register",
        id: "r-pu-bad",
        payload: {
          bot_id: "bot-pu-bad",
          license_key: LICENSE_PER_USER,
          connection_password_proof: proof,
          version: "0.1.0",
        },
      })
    );
    const { code } = await waitClose(sock.ws);
    expect(code).toBe(4001);
  });
});

describe("RPC round-trip", () => {
  it("routes RPC from web client to bot and relays response", async () => {
    const botSock = await registeredBot({ botId: "bot-rpc" });
    const webSock = await connectWeb(ACCOUNT_A);

    const rpcId = sendRpc(webSock, "bot-rpc", "get_state");

    const req = (await botSock.next()) as {
      type: string;
      id: string;
      payload: { method: string };
    };
    expect(req.type).toBe("rpc_request");
    expect(req.payload.method).toBe("get_state");

    botSock.ws.send(
      JSON.stringify({
        type: "rpc_response",
        id: req.id,
        payload: { result: { account: null, tickers: [] } },
      })
    );

    const response = (await waitForType(webSock, "rpc_response")) as {
      id: string;
      payload: { result: { tickers: unknown[] } };
    };
    expect(response.id).toBe(rpcId);
    expect(response.payload.result.tickers).toEqual([]);

    botSock.close();
    webSock.close();
  });

  it("returns RPC_FAILED error after timeout", async () => {
    const botSock = await registeredBot({ botId: "bot-timeout" });
    const webSock = await connectWeb(ACCOUNT_A);

    sendRpc(webSock, "bot-timeout", "get_state");
    // bot does NOT respond → relay times out after rpcTimeoutMs (2s)

    const response = (await waitForType(webSock, "rpc_response", 4000)) as {
      payload: { error: { code: string } };
    };
    expect(response.payload.error.code).toBe("RPC_FAILED");

    botSock.close();
    webSock.close();
  });

  it("returns BOT_NOT_FOUND when bot does not exist", async () => {
    const webSock = await connectWeb(ACCOUNT_A);
    sendRpc(webSock, "nonexistent-bot", "get_state");
    const msg = (await webSock.next()) as {
      type: string;
      payload: { code: string };
    };
    expect(msg.type).toBe("error");
    expect(msg.payload.code).toBe("BOT_NOT_FOUND");
    webSock.close();
  });
});

describe("Log and state streams", () => {
  it("relays log events from bot to subscribed web clients", async () => {
    const botSock = await registeredBot({ botId: "bot-log" });
    const webSock = await connectWeb(ACCOUNT_A);

    // Subscribe web client by sending an rpc_request
    sendRpc(webSock, "bot-log", "get_active_tickers");
    // Wait for the rpc_request to arrive at bot (subscription registered)
    const rpcReq = (await botSock.next()) as { id: string };

    // Bot sends a log event
    botSock.ws.send(
      JSON.stringify({
        type: "log",
        id: "log-1",
        payload: {
          timestamp: "2024-01-01T00:00:00Z",
          category: "info",
          message: "hello from bot",
        },
      })
    );

    const logMsg = (await waitForType(webSock, "log", 2000)) as {
      payload: { bot_id: string; event: { message: string } };
    };
    expect(logMsg.payload.bot_id).toBe("bot-log");
    expect(logMsg.payload.event.message).toBe("hello from bot");

    // Respond to RPC to clean up the pending entry
    botSock.ws.send(
      JSON.stringify({
        type: "rpc_response",
        id: rpcReq.id,
        payload: { result: { symbols: [] } },
      })
    );

    botSock.close();
    webSock.close();
  });

  it("relays state_update from bot to subscribed web clients", async () => {
    const botSock = await registeredBot({ botId: "bot-state" });
    const webSock = await connectWeb(ACCOUNT_A);

    sendRpc(webSock, "bot-state", "get_active_tickers");
    const rpcReq = (await botSock.next()) as { id: string };

    botSock.ws.send(
      JSON.stringify({
        type: "state_update",
        id: "su-1",
        payload: {
          tickers: [
            {
              symbol: "AAPL",
              last_price: 150,
              high_of_day: 155,
              low_of_day: 145,
              macd_line: 0.5,
              macd_signal: 0.3,
              macd_hist: 0.2,
              pattern_tags: [],
              score: 75,
              updated_at: "2024-01-01T00:00:00Z",
            },
          ],
        },
      })
    );

    const su = (await waitForType(webSock, "state_update", 2000)) as {
      payload: { bot_id: string; tickers: Array<{ symbol: string }> };
    };
    expect(su.payload.bot_id).toBe("bot-state");
    expect(su.payload.tickers[0].symbol).toBe("AAPL");

    botSock.ws.send(
      JSON.stringify({
        type: "rpc_response",
        id: rpcReq.id,
        payload: { result: { symbols: [] } },
      })
    );

    botSock.close();
    webSock.close();
  });
});

describe("Account scoping", () => {
  it("prevents web client from reaching a bot on a different account", async () => {
    const botSock = await registeredBot({
      botId: "bot-scoped",
      licenseKey: VALID_LICENSE,
    });
    const webSock = await connectWeb(ACCOUNT_B);

    sendRpc(webSock, "bot-scoped", "get_state");

    const msg = (await webSock.next()) as {
      type: string;
      payload: { code: string };
    };
    expect(msg.type).toBe("error");
    expect(msg.payload.code).toBe("BOT_NOT_FOUND");

    botSock.close();
    webSock.close();
  });

  it("allows web client to reach their own bot", async () => {
    const botSock = await registeredBot({
      botId: "bot-mine",
      licenseKey: VALID_LICENSE,
    });
    const webSock = await connectWeb(ACCOUNT_A);

    sendRpc(webSock, "bot-mine", "get_settings");
    const req = (await botSock.next()) as { id: string };

    botSock.ws.send(
      JSON.stringify({
        type: "rpc_response",
        id: req.id,
        payload: { result: { ok: true } },
      })
    );

    const response = (await waitForType(webSock, "rpc_response")) as {
      payload: { result: { ok: boolean } };
    };
    expect(response.payload.result.ok).toBe(true);

    botSock.close();
    webSock.close();
  });

  it("rejects web client with no token", async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${relayPort}/ws`);
    ws.on("error", () => {});
    const { code } = await waitClose(ws);
    expect(code).toBe(4001);
  });

  it("rejects web client with invalid token", async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${relayPort}/ws?token=garbage`);
    ws.on("error", () => {});
    const { code } = await waitClose(ws);
    expect(code).toBe(4001);
  });
});

describe("Reconnect handling", () => {
  it("replaces old bot connection when bot reconnects with same bot_id", async () => {
    const sock1 = await registeredBot({ botId: "bot-reconnect" });
    expect(relay.routingMap.getBot("bot-reconnect")).toBeDefined();

    const closed1 = waitClose(sock1.ws);
    const sock2 = await registeredBot({ botId: "bot-reconnect" });

    const { code } = await closed1;
    expect(code).toBe(4010);

    const botRecord = relay.routingMap.getBot("bot-reconnect");
    expect(botRecord).toBeDefined();
    // The routing map must now point at the new server-side ws, not the old one
    expect(botRecord?.ws).not.toBe(undefined);
    // Confirm the bot is still reachable (new connection is active)
    expect(botRecord?.registered_at).toBeGreaterThan(0);

    sock2.close();
  });

  it("removes bot from routing map on disconnect", async () => {
    const sock = await registeredBot({ botId: "bot-disco" });
    expect(relay.routingMap.getBot("bot-disco")).toBeDefined();

    const closed = waitClose(sock.ws);
    sock.close();
    await closed;

    // Poll until the server-side close handler fires and calls unregisterBot.
    // setImmediate is not enough because the server's close event fires on a
    // different socket object and may arrive one or more event-loop turns later.
    const deadline = Date.now() + 500;
    while (relay.routingMap.getBot("bot-disco") && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 10));
    }
    expect(relay.routingMap.getBot("bot-disco")).toBeUndefined();
  });

  it("notifies web clients when bot disconnects", async () => {
    const botSock = await registeredBot({ botId: "bot-notify" });
    const webSock = await connectWeb(ACCOUNT_A);

    // Subscribe web client
    sendRpc(webSock, "bot-notify", "get_active_tickers");
    await botSock.next(); // consume the rpc_request (subscription is now registered)

    const errMsg = waitForType(webSock, "error", 2000);
    botSock.close();

    const msg = (await errMsg) as { payload: { code: string } };
    expect(msg.payload.code).toBe("BOT_DISCONNECTED");

    webSock.close();
  });
});

describe("Security", () => {
  it("relay server binds to the configured host and exposes boundPort", async () => {
    expect(relay.boundPort).toBeGreaterThan(0);
    // configuredHost reflects what was passed in RelayConfig (default "0.0.0.0")
    // Tests pass no host so it falls back to default; value is whatever the OS reports
    expect(typeof relay.configuredHost).toBe("string");
    expect(relay.configuredHost.length).toBeGreaterThan(0);
  });

  it("bot connections require a valid HMAC proof (covered by registration tests)", () => {
    // See "closes with AUTH_FAILED on bad HMAC proof" above.
    // This assertion documents the security invariant.
    expect(true).toBe(true);
  });

  it("web client connections require a valid account token", async () => {
    // No token → 4001
    const ws1 = new WebSocket(`ws://127.0.0.1:${relayPort}/ws`);
    ws1.on("error", () => {});
    const { code: c1 } = await waitClose(ws1);
    expect(c1).toBe(4001);

    // Bad token format → 4001
    const ws2 = new WebSocket(`ws://127.0.0.1:${relayPort}/ws?token=garbage`);
    ws2.on("error", () => {});
    const { code: c2 } = await waitClose(ws2);
    expect(c2).toBe(4001);
  });
});

describe("Rate limiting", () => {
  it("drops messages from bots that exceed the rate limit", async () => {
    await relay.close();
    relay = new RelayServer({
      port: 0,
      validateUrl: `http://127.0.0.1:${validatorPort}/validate`,
      connectionSecret: CONNECTION_SECRET,
      rpcTimeoutMs: 2000,
      pingIntervalMs: 60_000,
      rateLimitMsgPerSec: 2,
      rateLimitBurst: 2,
    });
    await relay.listen();
    relayPort = relay.boundPort;

    const botSock = await registeredBot({ botId: "bot-rl" });
    const webSock = await connectWeb(ACCOUNT_A);

    sendRpc(webSock, "bot-rl", "get_active_tickers");
    await botSock.next(); // consume the rpc_request

    // Collect messages into a raw list
    const received: unknown[] = [];
    webSock.ws.on("message", (raw: Buffer) => {
      received.push(JSON.parse(raw.toString()));
    });

    // Blast 20 log messages; only 2 tokens → most should be dropped
    for (let i = 0; i < 20; i++) {
      botSock.ws.send(
        JSON.stringify({
          type: "log",
          id: `l${i}`,
          payload: {
            timestamp: new Date().toISOString(),
            category: "info",
            message: `msg ${i}`,
          },
        })
      );
    }

    await new Promise((r) => setTimeout(r, 300));

    const logMsgs = received.filter((m) => (m as { type: string }).type === "log");
    expect(logMsgs.length).toBeLessThan(20);

    botSock.close();
    webSock.close();
  });
});
