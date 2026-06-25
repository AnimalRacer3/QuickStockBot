import type { BotRecord, WebClientRecord, PendingRpc } from "./types.js";

/**
 * In-memory routing map for v1.
 * NOTE: Redis is needed for multi-instance scale.
 *
 * Bot stable URL/id is the bot_id UUID from the bot's settings file.
 * Bots are reachable at: ws://<relay-host>/bot/<bot_id> (or via register frame).
 */
export class RoutingMap {
  // bot_id → BotRecord
  private bots = new Map<string, BotRecord>();
  // account_id → Set<bot_id> (one account can have multiple bots)
  private accountBots = new Map<string, Set<string>>();
  // web clients attached to a bot: bot_id → Set<WebClientRecord>
  private botSubscribers = new Map<string, Set<WebClientRecord>>();
  // pending RPC calls: rpc_id → PendingRpc
  private pendingRpcs = new Map<string, PendingRpc>();

  registerBot(record: BotRecord): void {
    this.bots.set(record.bot_id, record);
    if (!this.accountBots.has(record.account_id)) {
      this.accountBots.set(record.account_id, new Set());
    }
    this.accountBots.get(record.account_id)!.add(record.bot_id);
  }

  unregisterBot(botId: string): void {
    const record = this.bots.get(botId);
    if (record) {
      this.accountBots.get(record.account_id)?.delete(botId);
      this.bots.delete(botId);
    }
    // Notify any subscribed web clients that bot disconnected
    const subs = this.botSubscribers.get(botId);
    if (subs) {
      for (const client of subs) {
        if (client.ws.readyState === 1 /* OPEN */) {
          client.ws.send(
            JSON.stringify({
              type: "error",
              id: "system",
              payload: { code: "BOT_DISCONNECTED", message: "Bot disconnected" },
            }),
          );
        }
      }
      this.botSubscribers.delete(botId);
    }
    // Reject any pending RPCs for this bot
    for (const [id, pending] of this.pendingRpcs) {
      clearTimeout(pending.timeout);
      pending.reject(new Error("Bot disconnected"));
      this.pendingRpcs.delete(id);
    }
  }

  getBot(botId: string): BotRecord | undefined {
    return this.bots.get(botId);
  }

  getBotByAccountId(accountId: string): BotRecord[] {
    const ids = this.accountBots.get(accountId);
    if (!ids) return [];
    return [...ids].map((id) => this.bots.get(id)).filter(Boolean) as BotRecord[];
  }

  /** Returns the bot only if it belongs to the given account (scoping check). */
  getBotScoped(botId: string, accountId: string): BotRecord | undefined {
    const record = this.bots.get(botId);
    if (!record || record.account_id !== accountId) return undefined;
    return record;
  }

  updateBotPing(botId: string): void {
    const record = this.bots.get(botId);
    if (record) record.last_ping_at = Date.now();
  }

  // ─── Web client subscriber management ──────────────────────────────────────

  addSubscriber(botId: string, client: WebClientRecord): void {
    if (!this.botSubscribers.has(botId)) {
      this.botSubscribers.set(botId, new Set());
    }
    this.botSubscribers.get(botId)!.add(client);
  }

  removeSubscriber(botId: string, client: WebClientRecord): void {
    this.botSubscribers.get(botId)?.delete(client);
  }

  getSubscribers(botId: string): Set<WebClientRecord> {
    return this.botSubscribers.get(botId) ?? new Set();
  }

  // ─── Pending RPC tracking ───────────────────────────────────────────────────

  addPending(rpcId: string, pending: PendingRpc): void {
    this.pendingRpcs.set(rpcId, pending);
  }

  resolvePending(rpcId: string, result: unknown): boolean {
    const pending = this.pendingRpcs.get(rpcId);
    if (!pending) return false;
    clearTimeout(pending.timeout);
    this.pendingRpcs.delete(rpcId);
    pending.resolve(result);
    return true;
  }

  rejectPending(rpcId: string, err: Error): boolean {
    const pending = this.pendingRpcs.get(rpcId);
    if (!pending) return false;
    clearTimeout(pending.timeout);
    this.pendingRpcs.delete(rpcId);
    pending.reject(err);
    return true;
  }

  removePending(rpcId: string): void {
    this.pendingRpcs.delete(rpcId);
  }

  findBotIdByWs(ws: unknown): string | undefined {
    for (const [id, record] of this.bots) {
      if (record.ws === ws) return id;
    }
    return undefined;
  }

  get botCount(): number {
    return this.bots.size;
  }
}
