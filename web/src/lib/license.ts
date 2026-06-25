import { randomBytes } from "crypto";
import type Database from "better-sqlite3";

export type LicenseStatus = "active" | "revoked" | "expired";

export interface License {
  key: string;
  userId: string;
  status: LicenseStatus;
  issuedAt: string;
  expiresAt: string | null;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
  subscriptionStatus: string;
  createdAt: string;
}

/** Generates a cryptographically random key: QSB-XXXX-XXXX-XXXX-XXXX */
export function generateLicenseKey(): string {
  const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  const segment = (): string =>
    Array.from({ length: 4 }, () => CHARS[randomBytes(1)[0] % CHARS.length]).join("");
  return `QSB-${segment()}-${segment()}-${segment()}-${segment()}`;
}

type Row<T> = T | undefined;

interface LicenseRow {
  key: string;
  user_id: string;
  status: string;
  issued_at: string;
  expires_at: string | null;
}

interface UserRow {
  id: string;
  email: string;
  name: string | null;
  subscription_status: string;
  created_at: string;
}

function rowToLicense(row: LicenseRow): License {
  return {
    key: row.key,
    userId: row.user_id,
    status: row.status as LicenseStatus,
    issuedAt: row.issued_at,
    expiresAt: row.expires_at,
  };
}

function rowToUser(row: UserRow): User {
  return {
    id: row.id,
    email: row.email,
    name: row.name,
    subscriptionStatus: row.subscription_status,
    createdAt: row.created_at,
  };
}

export function createLicenseRepository(db: Database.Database) {
  const stmts = {
    insertLicense: db.prepare(
      `INSERT INTO licenses (key, user_id, status, issued_at, expires_at)
       VALUES (?, ?, 'active', ?, ?)`
    ),
    getLicense: db.prepare<[string], LicenseRow>(
      `SELECT key, user_id, status, issued_at, expires_at FROM licenses WHERE key = ?`
    ),
    updateStatus: db.prepare(`UPDATE licenses SET status = ? WHERE key = ? AND status != ?`),
    insertUser: db.prepare(
      `INSERT INTO users (id, email, name, subscription_status, created_at)
       VALUES (?, ?, ?, 'active', ?)`
    ),
    getUserByEmail: db.prepare<[string], UserRow>(
      `SELECT id, email, name, subscription_status, created_at FROM users WHERE email = ?`
    ),
    getUserById: db.prepare<[string], UserRow>(
      `SELECT id, email, name, subscription_status, created_at FROM users WHERE id = ?`
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
     * An expired-by-date license is reported as 'expired' even if DB status is 'active'.
     * Returns null if the key doesn't exist.
     */
    validateLicense(key: string): LicenseStatus | null {
      const row: Row<LicenseRow> = stmts.getLicense.get(key);
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
      const row: Row<LicenseRow> = stmts.getLicense.get(key);
      return row ? rowToLicense(row) : null;
    },

    getUserByEmail(email: string): User | null {
      const row: Row<UserRow> = stmts.getUserByEmail.get(email);
      return row ? rowToUser(row) : null;
    },

    getUserById(id: string): User | null {
      const row: Row<UserRow> = stmts.getUserById.get(id);
      return row ? rowToUser(row) : null;
    },

    createUser(id: string, email: string, name?: string): User {
      const createdAt = new Date().toISOString();
      stmts.insertUser.run(id, email, name ?? null, createdAt);
      return {
        id,
        email,
        name: name ?? null,
        subscriptionStatus: "active",
        createdAt,
      };
    },
  };
}
