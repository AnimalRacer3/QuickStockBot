import { describe, it, expect, beforeEach } from "vitest";
import { checkRateLimit, clearRateLimitBuckets } from "./rate-limit";

describe("checkRateLimit", () => {
  beforeEach(() => {
    clearRateLimitBuckets();
  });

  it("allows requests up to maxTokens burst", () => {
    for (let i = 0; i < 5; i++) {
      expect(checkRateLimit("test-ip", 5, 1)).toBe(true);
    }
  });

  it("blocks requests beyond maxTokens burst", () => {
    for (let i = 0; i < 5; i++) checkRateLimit("test-ip", 5, 1);
    expect(checkRateLimit("test-ip", 5, 1)).toBe(false);
  });

  it("independent buckets per key", () => {
    for (let i = 0; i < 5; i++) checkRateLimit("ip-a", 5, 1);
    // ip-a exhausted, ip-b still has tokens
    expect(checkRateLimit("ip-a", 5, 1)).toBe(false);
    expect(checkRateLimit("ip-b", 5, 1)).toBe(true);
  });

  it("clearRateLimitBuckets resets a single key", () => {
    for (let i = 0; i < 5; i++) checkRateLimit("ip-x", 5, 1);
    expect(checkRateLimit("ip-x", 5, 1)).toBe(false);
    clearRateLimitBuckets("ip-x");
    expect(checkRateLimit("ip-x", 5, 1)).toBe(true);
  });
});
