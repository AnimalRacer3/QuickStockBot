/** In-memory token-bucket rate limiter for web API endpoints. */

const buckets = new Map<string, { tokens: number; last: number }>();

/**
 * Returns true if the request is allowed; false if rate-limited.
 * @param key       Bucket key (typically IP address)
 * @param maxTokens Max burst size
 * @param refillPerSec Tokens refilled per second
 */
export function checkRateLimit(key: string, maxTokens = 10, refillPerSec = 10 / 60): boolean {
  const now = Date.now();
  let b = buckets.get(key);
  if (!b) {
    b = { tokens: maxTokens, last: now };
    buckets.set(key, b);
  }
  const elapsed = (now - b.last) / 1000;
  b.tokens = Math.min(maxTokens, b.tokens + elapsed * refillPerSec);
  b.last = now;
  if (b.tokens < 1) return false;
  b.tokens -= 1;
  return true;
}

/** Clear rate limit state — intended for tests only. */
export function clearRateLimitBuckets(key?: string): void {
  if (key !== undefined) {
    buckets.delete(key);
  } else {
    buckets.clear();
  }
}
