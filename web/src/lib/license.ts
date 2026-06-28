import { randomBytes } from "crypto";
import type Database from "better-sqlite3";

export type LicenseStatus = "active" | "revoked" | "expired";

export interface License {
  key: string;
  userId: string;
  status: LicenseStatus;
  issuedAt: string;
  expiresAt: string | null;
  connectionPassword: string | null;
}

/** Generates a cryptographically random key: QSB-XXXX-XXXX-XXXX-XXXX */
export function generateLicenseKey(): string {
  const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  const segment = (): string =>
    Array.from({ length: 4 }, () => CHARS[randomBytes(1)[0] % CHARS.length]).join("");
  return `QSB-${segment()}-${segment()}-${segment()}-${segment()}`;
}

interface LicenseRow {
  key: string;
  user_id: string;
  status: string;
  issued_at: string;
  expires_at: string | null;
  connection_password: string | null;
}

function rowToLicense(row: LicenseRow): License {
  return {
    key: row.key,
    userId: row.user_id,
    status: row.status as LicenseStatus,
    issuedAt: row.issued_at,
    expiresAt: row.expires_at,
    connectionPassword: row.connection_password ?? null,
  };
}

export function createLicenseRepository(db: Database.Database) {
  const stmts = {
    insertLicense: db.prepare(
      `INSERT INTO licenses (key, user_id, status, issued_at, expires_at)
       VALUES (?, ?, 'active', ?, ?)`
    ),
    getLicense: db.prepare<[string], LicenseRow>(
      `SELECT key, user_id, status, issued_at, expires_at, connection_password
       FROM licenses WHERE key = ?`
    ),
    getByUserId: db.prepare<[string], LicenseRow>(
      `SELECT key, user_id, status, issued_at, expires_at, connection_password
       FROM licenses WHERE user_id = ? AND status = 'active'
       ORDER BY issued_at DESC LIMIT 1`
    ),
    updateStatus: db.prepare(`UPDATE licenses SET status = ? WHERE key = ? AND status != ?`),
    setConnectionPassword: db.prepare(
      `UPDATE licenses SET connection_password = ? WHERE key = ?`
    ),
  };

  return {
    issueLicense(userId: string, expiresAt?: string): License {
      const key = generateLicenseKey();
      const issuedAt = new Date().toISOString();
      stmts.insertLicense.run(key, userId, issuedAt, expiresAt ?? null);
      return {
        key,
        userId,
        status: "active",
        issuedAt,
        expiresAt: expiresAt ?? null,
      };
    },

    /**
     * Returns the effective status of a license.
     * An expired-by-date license reports as 'expired' even if DB status is 'active'.
     * Returns null if the key doesn't exist.
     */
    validateLicense(key: string): LicenseStatus | null {
      const row = stmts.getLicense.get(key);
      if (!row) return null;
      if (row.status === "revoked") return "revoked";
      if (row.expires_at && new Date(row.expires_at) < new Date()) return "expired";
      return "active";
    },

    revokeLicense(key: string): boolean {
      const result = stmts.updateStatus.run("revoked", key, "revoked");
      return result.changes > 0;
    },

    getLicense(key: string): License | null {
      const row = stmts.getLicense.get(key);
      return row ? rowToLicense(row) : null;
    },

    getLicenseByUserId(userId: string): License | null {
      const row = stmts.getByUserId.get(userId);
      return row ? rowToLicense(row) : null;
    },

    setConnectionPassword(key: string, password: string): boolean {
      const result = stmts.setConnectionPassword.run(password, key);
      return result.changes > 0;
    },
  };
}
