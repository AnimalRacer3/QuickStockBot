// @vitest-environment node
import { describe, it, expect, beforeEach } from "vitest";
import { createDb } from "../db";
import { generateLicenseKey, createLicenseRepository } from "../license";
import type Database from "better-sqlite3";

// ── Key generation ──────────────────────────────────────────────────────────

describe("generateLicenseKey", () => {
  it("matches QSB-XXXX-XXXX-XXXX-XXXX format", () => {
    const key = generateLicenseKey();
    expect(key).toMatch(
      /^QSB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/,
    );
  });

  it("generates unique keys across 1 000 iterations", () => {
    const keys = new Set(
      Array.from({ length: 1000 }, () => generateLicenseKey()),
    );
    expect(keys.size).toBe(1000);
  });
});

// ── Repository ──────────────────────────────────────────────────────────────

describe("LicenseRepository", () => {
  let db: Database.Database;
  let repo: ReturnType<typeof createLicenseRepository>;
  const userId = "user-001";

  beforeEach(() => {
    db = createDb(); // in-memory; fresh each test
    repo = createLicenseRepository(db);
    repo.createUser(userId, "test@example.com", "Test User");
  });

  // ── issueLicense ───────────────────────────────────────────────────────

  describe("issueLicense", () => {
    it("returns a license with active status and correct userId", () => {
      const lic = repo.issueLicense(userId);
      expect(lic.status).toBe("active");
      expect(lic.userId).toBe(userId);
    });

    it("returns a key in the QSB- format", () => {
      expect(repo.issueLicense(userId).key).toMatch(/^QSB-/);
    });

    it("persists the license so getLicense returns it", () => {
      const issued = repo.issueLicense(userId);
      const fetched = repo.getLicense(issued.key);
      expect(fetched).not.toBeNull();
      expect(fetched!.key).toBe(issued.key);
      expect(fetched!.status).toBe("active");
    });

    it("produces distinct keys for consecutive calls", () => {
      const k1 = repo.issueLicense(userId).key;
      const k2 = repo.issueLicense(userId).key;
      expect(k1).not.toBe(k2);
    });

    it("stores the optional expiresAt when provided", () => {
      const future = new Date(Date.now() + 86_400_000).toISOString();
      const lic = repo.issueLicense(userId, future);
      expect(repo.getLicense(lic.key)!.expiresAt).toBe(future);
    });
  });

  // ── validateLicense ────────────────────────────────────────────────────

  describe("validateLicense", () => {
    it("returns 'active' for a freshly issued license", () => {
      const { key } = repo.issueLicense(userId);
      expect(repo.validateLicense(key)).toBe("active");
    });

    it("returns 'revoked' after the license is revoked", () => {
      const { key } = repo.issueLicense(userId);
      repo.revokeLicense(key);
      expect(repo.validateLicense(key)).toBe("revoked");
    });

    it("returns 'expired' when expires_at is in the past", () => {
      const yesterday = new Date(Date.now() - 86_400_000).toISOString();
      const { key } = repo.issueLicense(userId, yesterday);
      expect(repo.validateLicense(key)).toBe("expired");
    });

    it("returns 'active' when expires_at is in the future", () => {
      const tomorrow = new Date(Date.now() + 86_400_000).toISOString();
      const { key } = repo.issueLicense(userId, tomorrow);
      expect(repo.validateLicense(key)).toBe("active");
    });

    it("returns null for a key that does not exist", () => {
      expect(repo.validateLicense("QSB-0000-0000-0000-0000")).toBeNull();
    });
  });

  // ── revokeLicense ──────────────────────────────────────────────────────

  describe("revokeLicense", () => {
    it("returns true on first revocation", () => {
      const { key } = repo.issueLicense(userId);
      expect(repo.revokeLicense(key)).toBe(true);
    });

    it("returns false when called again on an already-revoked license", () => {
      const { key } = repo.issueLicense(userId);
      repo.revokeLicense(key);
      expect(repo.revokeLicense(key)).toBe(false);
    });

    it("returns false for an unknown key", () => {
      expect(repo.revokeLicense("QSB-0000-0000-0000-0000")).toBe(false);
    });

    it("does not affect other licenses", () => {
      const k1 = repo.issueLicense(userId).key;
      const k2 = repo.issueLicense(userId).key;
      repo.revokeLicense(k1);
      expect(repo.validateLicense(k2)).toBe("active");
    });
  });

  // ── createUser / getUserByEmail ────────────────────────────────────────

  describe("createUser / getUserByEmail", () => {
    it("retrieves a user that was created", () => {
      const user = repo.getUserByEmail("test@example.com");
      expect(user).not.toBeNull();
      expect(user!.id).toBe(userId);
      expect(user!.name).toBe("Test User");
    });

    it("returns null for an unknown email", () => {
      expect(repo.getUserByEmail("nobody@example.com")).toBeNull();
    });
  });
});
