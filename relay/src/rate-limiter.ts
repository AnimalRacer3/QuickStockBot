/**
 * Simple token-bucket rate limiter keyed by an arbitrary string (IP, bot_id, etc.).
 */
export class RateLimiter {
  private buckets = new Map<string, { tokens: number; last: number }>();

  constructor(
    private readonly maxTokens: number,
    private readonly refillRatePerSec: number,
  ) {}

  /**
   * Returns true if the request is allowed, false if rate-limited.
   * Consumes one token on each allowed call.
   */
  allow(key: string): boolean {
    const now = Date.now();
    let bucket = this.buckets.get(key);
    if (!bucket) {
      bucket = { tokens: this.maxTokens, last: now };
      this.buckets.set(key, bucket);
    }
    // Refill tokens based on elapsed time
    const elapsed = (now - bucket.last) / 1000;
    bucket.tokens = Math.min(
      this.maxTokens,
      bucket.tokens + elapsed * this.refillRatePerSec,
    );
    bucket.last = now;

    if (bucket.tokens < 1) return false;
    bucket.tokens -= 1;
    return true;
  }

  /** Remove stale entries to prevent unbounded memory growth. */
  cleanup(maxIdleMs = 60_000): void {
    const cutoff = Date.now() - maxIdleMs;
    for (const [key, bucket] of this.buckets) {
      if (bucket.last < cutoff) this.buckets.delete(key);
    }
  }
}
