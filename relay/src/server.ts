import { WebSocketServer, WebSocket } from "ws";
import { createServer, type Server } from "http";
import { randomUUID } from "crypto";
import { generateNonce, verifyHmac, validateLicense } from "./auth.js";
import { RoutingMap } from "./routing.js";
import { RateLimiter } from "./rate-limiter.js";
import { logger } from "./logger.js";
import type {
  BotRecord,
  WebClientRecord,
  WebToRelayMessage,
  RelayToWebMessage,
  Envelope,
  RegisterPayload,
  RpcResponsePayload,
  StateUpdatePayload,
  LogEvent,
} from "./types.js";

export interface RelayConfig {
  port: number;
  /** Bind address — "0.0.0.0" for Railway/public, "127.0.0.1" for local-only dev */
  host?: string;
  /** SaaS validation endpoint URL (Section 12) */
  validateUrl: string;
  /** HMAC secret shared with bot instances; skip proof check if empty */
  connectionSecret?: string;
  /** Shared secret sent to the SaaS validate endpoint; bypasses Cloudflare bot protection */
  saasSecret?: string;
  /** RPC round-trip timeout in ms */
  rpcTimeoutMs?: number;
  /** Ping interval in ms */
  pingIntervalMs?: number;
  /** Close if no pong within this ms after ping */
  heartbeatTimeoutMs?: number;
  /** Max messages per second per connection */
  rateLimitMsgPerSec?: number;
  /** Max burst tokens for rate limiter */
  rateLimitBurst?: number;
}

const DEFAULTS = {
  rpcTimeoutMs: 15_000,
  pingIntervalMs: 30_000,
  heartbeatTimeoutMs: 10_000,
  rateLimitMsgPerSec: 20,
  rateLimitBurst: 40,
} as const;

interface PendingBot {
  nonce: string;
  timeout: ReturnType<typeof setTimeout>;
}

export class RelayServer {
  private httpServer: Server;
  private botWss: WebSocketServer;
  private webWss: WebSocketServer;
  private routing: RoutingMap;
  private botRateLimiter: RateLimiter;
  private webRateLimiter: RateLimiter;
  private pingInterval?: ReturnType<typeof setInterval>;
  private cleanupInterval?: ReturnType<typeof setInterval>;
  /** Quick ws → bot_id lookup without scanning routing map */
  private wsToBotId = new Map<WebSocket, string>();
  private cfg: Required<RelayConfig>;
  private boundHost: string = "0.0.0.0";

  constructor(config: RelayConfig) {
    this.cfg = {
      host: "0.0.0.0",
      connectionSecret: "",
      saasSecret: "",
      rpcTimeoutMs: DEFAULTS.rpcTimeoutMs,
      pingIntervalMs: DEFAULTS.pingIntervalMs,
      heartbeatTimeoutMs: DEFAULTS.heartbeatTimeoutMs,
      rateLimitMsgPerSec: DEFAULTS.rateLimitMsgPerSec,
      rateLimitBurst: DEFAULTS.rateLimitBurst,
      ...config,
    };

    this.routing = new RoutingMap();
    this.botRateLimiter = new RateLimiter(this.cfg.rateLimitBurst, this.cfg.rateLimitMsgPerSec);
    this.webRateLimiter = new RateLimiter(this.cfg.rateLimitBurst, this.cfg.rateLimitMsgPerSec);

    this.httpServer = createServer((_req, res) => {
      res.writeHead(200);
      res.end("QuickStockBot Relay");
    });

    this.botWss = new WebSocketServer({ noServer: true });
    this.webWss = new WebSocketServer({ noServer: true });

    this.httpServer.on("upgrade", (req, socket, head) => {
      const url = req.url ?? "/";
      if (url === "/bot" || url.startsWith("/bot?")) {
        this.botWss.handleUpgrade(req, socket, head, (ws) => {
          this.botWss.emit("connection", ws, req);
        });
      } else if (url === "/ws" || url.startsWith("/ws?")) {
        this.webWss.handleUpgrade(req, socket, head, (ws) => {
          this.webWss.emit("connection", ws, req);
        });
      } else {
        socket.destroy();
      }
    });

    this.botWss.on("connection", (ws) => this.handleBotConnection(ws));
    this.webWss.on("connection", (ws, req) =>
      this.handleWebConnection(ws, req as { url?: string })
    );
  }

  // ─── Bot connection handler ─────────────────────────────────────────────────

  private handleBotConnection(ws: WebSocket): void {
    const nonce = generateNonce();
    const pending: PendingBot = {
      nonce,
      timeout: setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(4001, "Registration timeout");
        }
      }, 15_000),
    };

    this.send(ws, {
      type: "auth_challenge",
      id: randomUUID(),
      payload: { nonce },
    });

    ws.on("message", (raw) => {
      this.handleBotMessage(ws, raw.toString(), pending);
    });

    ws.on("pong", () => {
      const botId = this.wsToBotId.get(ws);
      if (botId) this.routing.updateBotPing(botId);
    });

    ws.on("close", () => {
      clearTimeout(pending.timeout);
      const botId = this.wsToBotId.get(ws);
      if (botId) {
        logger.info("Bot disconnected", { bot_id: botId });
        this.routing.unregisterBot(botId);
        this.wsToBotId.delete(ws);
      }
    });

    ws.on("error", (err) => {
      logger.error("Bot socket error", { err: err.message });
    });
  }

  private handleBotMessage(ws: WebSocket, raw: string, pending: PendingBot): void {
    let msg: Envelope;
    try {
      msg = JSON.parse(raw) as Envelope;
    } catch {
      ws.close(4002, "Invalid JSON");
      return;
    }

    const botId = this.wsToBotId.get(ws);

    if (!botId) {
      if (msg.type !== "register") {
        this.send(ws, {
          type: "error",
          id: msg.id ?? randomUUID(),
          payload: { code: "NOT_REGISTERED", message: "Send register first" },
        });
        ws.close(4003, "NOT_REGISTERED");
        return;
      }
      void this.handleRegister(ws, msg as Envelope<"register", RegisterPayload>, pending);
      return;
    }

    if (!this.botRateLimiter.allow(botId)) {
      logger.warn("Bot rate limited", { botId });
      return;
    }

    this.routing.updateBotPing(botId);

    switch (msg.type) {
      case "rpc_response":
        this.handleRpcResponse(botId, msg as Envelope<"rpc_response", RpcResponsePayload>);
        break;

      case "log":
        this.broadcastToWebClients(botId, {
          type: "log",
          id: randomUUID(),
          payload: {
            bot_id: botId,
            event: (msg as Envelope<"log", LogEvent>).payload,
          },
        });
        break;

      case "state_update":
        this.broadcastToWebClients(botId, {
          type: "state_update",
          id: randomUUID(),
          payload: {
            bot_id: botId,
            ...(msg as Envelope<"state_update", StateUpdatePayload>).payload,
          },
        });
        break;

      default:
        logger.warn("Unknown bot message type", { type: msg.type, botId });
    }
  }

  private async handleRegister(
    ws: WebSocket,
    msg: Envelope<"register", RegisterPayload>,
    pending: PendingBot
  ): Promise<void> {
    const { bot_id, license_key, connection_password_proof, version } = msg.payload ?? {};

    if (!bot_id || !license_key || !connection_password_proof || !version) {
      ws.close(4004, "AUTH_FAILED: missing fields");
      return;
    }

    // Validate license first so we can retrieve the per-user connection password.
    const licenseResult = await validateLicense(
      license_key,
      bot_id,
      this.cfg.validateUrl,
      this.cfg.saasSecret || undefined
    );

    if (!licenseResult.valid || !licenseResult.account_id) {
      const reason = licenseResult.error ?? "license invalid";
      logger.warn("Bot auth failed: invalid license, validation url: " + this.cfg.validateUrl + " Saas Secret: " + this.cfg.saasSecret, { bot_id, error: reason });

      const closeReason =
        reason === "license not found"
          ? "AUTH_FAILED: license key not found — seed it via POST /api/licenses/seed on the web app"
          : reason.startsWith("license is ")
            ? `AUTH_FAILED: ${reason} — check your LICENSE_KEY or renew your subscription`
            : `AUTH_FAILED: license validation failed (${reason}) — check SAAS_VALIDATE_URL on the relay`;
      ws.close(4001, closeReason);
      return;
    }

    // Determine which secret to use for HMAC verification.
    // Per-user password (from the SaaS) takes precedence over the global shared secret.
    const hmacSecret = licenseResult.connection_password || this.cfg.connectionSecret;

    if (hmacSecret) {
      if (!verifyHmac(pending.nonce, hmacSecret, connection_password_proof)) {
        logger.warn("Bot auth failed: bad HMAC proof", { bot_id });
        ws.close(
          4001,
          licenseResult.connection_password
            ? "AUTH_FAILED: wrong CONNECTION_PASSWORD — it must match the password you set during installation"
            : "AUTH_FAILED: wrong CONNECTION_PASSWORD — it must match RELAY_CONNECTION_SECRET on the relay server"
        );
        return;
      }
    } else {
      // Neither per-user password nor global secret is configured — reject for safety.
      logger.warn("Bot auth failed: no connection password configured", { bot_id });
      ws.close(
        4001,
        "AUTH_FAILED: no connection password set for this license — " +
          "run the installer or set one via POST /api/licenses/set-password on the web app"
      );
      return;
    }

    clearTimeout(pending.timeout);

    const existing = this.routing.getBot(bot_id);
    if (existing) {
      logger.info("Replacing existing bot connection", { bot_id });
      this.wsToBotId.delete(existing.ws);
      existing.ws.close(4010, "Replaced by new connection");
      this.routing.unregisterBot(bot_id);
    }

    const record: BotRecord = {
      ws,
      bot_id,
      account_id: licenseResult.account_id,
      version,
      registered_at: Date.now(),
      last_ping_at: Date.now(),
    };

    this.routing.registerBot(record);
    this.wsToBotId.set(ws, bot_id);

    logger.info("Bot registered", {
      bot_id,
      account_id: licenseResult.account_id,
      version,
    });

    this.send(ws, {
      type: "registered",
      id: msg.id,
      payload: { bot_id },
    });
  }

  private handleRpcResponse(
    botId: string,
    msg: Envelope<"rpc_response", RpcResponsePayload>
  ): void {
    const resolved = this.routing.resolvePending(msg.id, msg.payload);
    if (!resolved) {
      logger.debug("rpc_response for unknown/expired id", {
        id: msg.id,
        botId,
      });
    }
  }

  // ─── Web client connection handler ──────────────────────────────────────────

  private handleWebConnection(ws: WebSocket, req: { url?: string }): void {
    const token = extractQueryParam(req.url ?? "", "token");
    const accountId = this.verifyWebToken(token);

    if (!accountId) {
      ws.close(4001, "Unauthorized");
      return;
    }

    const client: WebClientRecord = {
      ws,
      account_id: accountId,
      connected_at: Date.now(),
      last_ping_at: Date.now(),
    };

    const subscribedBots = new Set<string>();

    ws.on("message", (raw) => {
      if (!this.webRateLimiter.allow(accountId)) {
        logger.warn("Web client rate limited", { accountId });
        return;
      }
      client.last_ping_at = Date.now();
      this.handleWebMessage(ws, raw.toString(), client, subscribedBots);
    });

    ws.on("close", () => {
      for (const botId of subscribedBots) {
        this.routing.removeSubscriber(botId, client);
      }
    });

    ws.on("error", (err) => {
      logger.error("Web client error", { err: err.message });
    });

    logger.info("Web client connected", { accountId });
  }

  private handleWebMessage(
    ws: WebSocket,
    raw: string,
    client: WebClientRecord,
    subscribedBots: Set<string>
  ): void {
    let msg: WebToRelayMessage;
    try {
      msg = JSON.parse(raw) as WebToRelayMessage;
    } catch {
      ws.close(4002, "Invalid JSON");
      return;
    }

    if (msg.type !== "rpc_request") {
      this.sendWeb(ws, {
        type: "error",
        id: msg.id ?? randomUUID(),
        payload: { code: "UNKNOWN_TYPE", message: "Unknown message type" },
      });
      return;
    }

    const { bot_id, method, params } = msg.payload;

    const bot = this.routing.getBotScoped(bot_id, client.account_id);
    if (!bot) {
      this.sendWeb(ws, {
        type: "error",
        id: msg.id,
        payload: {
          code: "BOT_NOT_FOUND",
          message: "Bot not found or not in your account",
        },
      });
      return;
    }

    if (!subscribedBots.has(bot_id)) {
      subscribedBots.add(bot_id);
      this.routing.addSubscriber(bot_id, client);
    }

    const rpcId = msg.id;
    const rpcPromise = new Promise<unknown>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.routing.removePending(rpcId);
        reject(new Error("RPC timeout"));
      }, this.cfg.rpcTimeoutMs);
      this.routing.addPending(rpcId, { resolve, reject, timeout });
    });

    // Forward to bot (relay must not accept on bot's behalf)
    this.send(bot.ws, {
      type: "rpc_request",
      id: rpcId,
      payload: { method, params },
    });

    rpcPromise.then(
      (payload) => {
        // payload is the full RpcResponsePayload from the bot — forward as-is
        if (ws.readyState === WebSocket.OPEN) {
          this.sendWeb(ws, {
            type: "rpc_response",
            id: rpcId,
            payload: payload as { result?: unknown; error?: { code: string; message: string } },
          });
        }
      },
      (err: Error) => {
        if (ws.readyState === WebSocket.OPEN) {
          this.sendWeb(ws, {
            type: "rpc_response",
            id: rpcId,
            payload: { error: { code: "RPC_FAILED", message: err.message } },
          });
        }
      }
    );
  }

  private broadcastToWebClients(botId: string, msg: RelayToWebMessage): void {
    const subs = this.routing.getSubscribers(botId);
    for (const client of subs) {
      if (client.ws.readyState === WebSocket.OPEN) {
        this.sendWeb(client.ws, msg);
      }
    }
  }

  // ─── Token validation ────────────────────────────────────────────────────────
  // v1: accept "account:<account_id>" tokens issued by the SaaS (Section 12)
  // Production: verify a signed JWT against the SaaS session store

  private verifyWebToken(token: string | null): string | null {
    if (!token) return null;
    if (token.startsWith("account:")) {
      const accountId = token.slice("account:".length);
      return accountId || null;
    }
    return null;
  }

  // ─── Heartbeat ──────────────────────────────────────────────────────────────

  private startHeartbeat(): void {
    this.pingInterval = setInterval(() => {
      const staleThreshold = Date.now() - this.cfg.pingIntervalMs - this.cfg.heartbeatTimeoutMs;

      for (const ws of this.botWss.clients) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.ping();
          const botId = this.wsToBotId.get(ws);
          if (botId) {
            const rec = this.routing.getBot(botId);
            if (rec && rec.last_ping_at < staleThreshold) {
              logger.warn("Closing stale bot connection", { bot_id: botId });
              ws.terminate();
            }
          }
        }
      }

      for (const ws of this.webWss.clients) {
        if (ws.readyState === WebSocket.OPEN) ws.ping();
      }
    }, this.cfg.pingIntervalMs);
  }

  // ─── Lifecycle ───────────────────────────────────────────────────────────────

  listen(): Promise<void> {
    return new Promise((resolve) => {
      this.httpServer.listen(this.cfg.port, this.cfg.host, () => {
        const addr = this.httpServer.address();
        const port = typeof addr === "object" && addr ? addr.port : this.cfg.port;
        const host = typeof addr === "object" && addr ? addr.address : this.cfg.host;
        this.boundHost = host;
        logger.info(`Relay listening on ${host}:${port}`);
        this.startHeartbeat();
        this.cleanupInterval = setInterval(() => {
          this.botRateLimiter.cleanup();
          this.webRateLimiter.cleanup();
        }, 5 * 60_000);
        resolve();
      });
    });
  }

  close(): Promise<void> {
    clearInterval(this.pingInterval);
    clearInterval(this.cleanupInterval);
    // Terminate all open connections so the HTTP server can close cleanly
    for (const ws of this.botWss.clients) ws.terminate();
    for (const ws of this.webWss.clients) ws.terminate();
    return new Promise((resolve) => {
      this.botWss.close();
      this.webWss.close();
      this.httpServer.close(() => resolve());
    });
  }

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  private send(ws: WebSocket, msg: unknown): void {
    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(msg));
      } catch (err) {
        logger.error("ws.send failed", {
          err: err instanceof Error ? err.message : String(err),
        });
      }
    }
  }

  private sendWeb(ws: WebSocket, msg: RelayToWebMessage): void {
    this.send(ws, msg);
  }

  get routingMap(): RoutingMap {
    return this.routing;
  }

  /** The actual port the server bound to (useful when port:0 is used). */
  get boundPort(): number {
    const addr = this.httpServer.address();
    if (!addr || typeof addr === "string") throw new Error("Server not listening");
    return addr.port;
  }

  /** The actual bind address after listen() resolves. */
  get configuredHost(): string {
    return this.boundHost;
  }
}

function extractQueryParam(url: string, key: string): string | null {
  const idx = url.indexOf("?");
  if (idx === -1) return null;
  const params = new URLSearchParams(url.slice(idx + 1));
  return params.get(key);
}
