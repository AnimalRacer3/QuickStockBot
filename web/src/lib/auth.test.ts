// @vitest-environment node
import { describe, it, expect } from "vitest";
import {
  hashPassword,
  verifyPassword,
  generateToken,
  getClientIp,
  signSession,
  verifySession,
} from "./auth";

describe("hashPassword / verifyPassword", () => {
  it("hashes a password and verifies it correctly", async () => {
    const hash = await hashPassword("mypassword123");
    expect(hash).not.toBe("mypassword123");
    await expect(verifyPassword(hash, "mypassword123")).resolves.toBe(true);
  });

  it("rejects a wrong password", async () => {
    const hash = await hashPassword("correct-password");
    await expect(verifyPassword(hash, "wrong-password")).resolves.toBe(false);
  });

  it("produces different hashes for the same input (salt)", async () => {
    const h1 = await hashPassword("same");
    const h2 = await hashPassword("same");
    expect(h1).not.toBe(h2);
  });
});

describe("generateToken", () => {
  it("returns a 64-char hex string", () => {
    const token = generateToken();
    expect(token).toMatch(/^[0-9a-f]{64}$/);
  });

  it("returns unique values", () => {
    expect(generateToken()).not.toBe(generateToken());
  });
});

describe("getClientIp", () => {
  function makeRequest(headers: Record<string, string>) {
    return new Request("http://localhost/", { headers });
  }

  it("reads x-forwarded-for (first IP only)", () => {
    const req = makeRequest({ "x-forwarded-for": "1.2.3.4, 5.6.7.8" });
    expect(getClientIp(req)).toBe("1.2.3.4");
  });

  it("reads x-real-ip when no x-forwarded-for", () => {
    const req = makeRequest({ "x-real-ip": "9.10.11.12" });
    expect(getClientIp(req)).toBe("9.10.11.12");
  });

  it("returns 127.0.0.1 when no IP headers present", () => {
    const req = makeRequest({});
    expect(getClientIp(req)).toBe("127.0.0.1");
  });
});

describe("signSession / verifySession", () => {
  it("signs a payload and verifies it", async () => {
    const payload = { userId: "u1", email: "a@b.com", emailVerified: true };
    const token = await signSession(payload);
    const decoded = await verifySession(token);
    expect(decoded?.userId).toBe("u1");
    expect(decoded?.email).toBe("a@b.com");
    expect(decoded?.emailVerified).toBe(true);
  });

  it("returns null for a tampered token", async () => {
    const result = await verifySession("not.a.valid.jwt");
    expect(result).toBeNull();
  });

  it("returns null for an empty string", async () => {
    expect(await verifySession("")).toBeNull();
  });
});
