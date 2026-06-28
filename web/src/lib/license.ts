import { randomBytes } from "crypto";
import { prisma } from "./db";

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

type LicenseRow = {
  key: string;
  userId: string;
  status: string;
  issuedAt: Date;
  expiresAt: Date | null;
  connectionPassword: string | null;
};

function rowToLicense(row: LicenseRow): License {
  return {
    key: row.key,
    userId: row.userId,
    status: row.status as LicenseStatus,
    issuedAt: row.issuedAt.toISOString(),
    expiresAt: row.expiresAt ? row.expiresAt.toISOString() : null,
    connectionPassword: row.connectionPassword ?? null,
  };
}

export async function issueLicense(userId: string, expiresAt?: string): Promise<License> {
  const key = generateLicenseKey();
  const row = await prisma.license.create({
    data: {
      key,
      userId,
      status: "active",
      expiresAt: expiresAt ? new Date(expiresAt) : null,
    },
  });
  return rowToLicense(row);
}

/**
 * Returns the effective status of a license.
 * An expired-by-date license reports as 'expired' even if DB status is 'active'.
 * Returns null if the key doesn't exist.
 */
export async function validateLicense(key: string): Promise<LicenseStatus | null> {
  const row = await prisma.license.findUnique({ where: { key } });
  if (!row) return null;
  if (row.status === "revoked") return "revoked";
  if (row.expiresAt && row.expiresAt < new Date()) return "expired";
  return "active";
}

export async function revokeLicense(key: string): Promise<boolean> {
  const result = await prisma.license.updateMany({
    where: { key, status: { not: "revoked" } },
    data: { status: "revoked" },
  });
  return result.count > 0;
}

export async function getLicense(key: string): Promise<License | null> {
  const row = await prisma.license.findUnique({ where: { key } });
  return row ? rowToLicense(row) : null;
}

export async function getLicenseByUserId(userId: string): Promise<License | null> {
  const row = await prisma.license.findFirst({
    where: { userId, status: "active" },
    orderBy: { issuedAt: "desc" },
  });
  return row ? rowToLicense(row) : null;
}

export async function setConnectionPassword(key: string, password: string): Promise<boolean> {
  const result = await prisma.license.updateMany({
    where: { key },
    data: { connectionPassword: password },
  });
  return result.count > 0;
}
