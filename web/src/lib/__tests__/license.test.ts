// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";
import { generateLicenseKey, validateLicense } from "../license";
import { prisma } from "../db";

vi.mock("../db", () => ({
  prisma: {
    license: {
      findUnique: vi.fn(),
    },
  },
}));

const mockFindUnique = prisma.license.findUnique as ReturnType<typeof vi.fn>;

// ── Key generation ──────────────────────────────────────────────────────────

describe("generateLicenseKey", () => {
  it("matches QSB-XXXX-XXXX-XXXX-XXXX format", () => {
    const key = generateLicenseKey();
    expect(key).toMatch(/^QSB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/);
  });

  it("generates unique keys across 1 000 iterations", () => {
    const keys = new Set(Array.from({ length: 1000 }, () => generateLicenseKey()));
    expect(keys.size).toBe(1000);
  });
});

// ── validateLicense — expiry logic (Prisma mocked) ──────────────────────────

describe("validateLicense", () => {
  beforeEach(() => vi.resetAllMocks());

  it("returns null when the key does not exist", async () => {
    mockFindUnique.mockResolvedValue(null);
    expect(await validateLicense("QSB-0000-0000-0000-0000")).toBeNull();
  });

  it("returns 'active' for a fresh license with no expiry", async () => {
    mockFindUnique.mockResolvedValue({ status: "active", expiresAt: null });
    expect(await validateLicense("QSB-AAAA-AAAA-AAAA-AAAA")).toBe("active");
  });

  it("returns 'revoked' regardless of expiry", async () => {
    mockFindUnique.mockResolvedValue({
      status: "revoked",
      expiresAt: new Date(Date.now() + 86_400_000),
    });
    expect(await validateLicense("QSB-AAAA-AAAA-AAAA-AAAA")).toBe("revoked");
  });

  it("returns 'expired' when expiresAt is in the past", async () => {
    mockFindUnique.mockResolvedValue({
      status: "active",
      expiresAt: new Date(Date.now() - 86_400_000),
    });
    expect(await validateLicense("QSB-AAAA-AAAA-AAAA-AAAA")).toBe("expired");
  });

  it("returns 'active' when expiresAt is in the future", async () => {
    mockFindUnique.mockResolvedValue({
      status: "active",
      expiresAt: new Date(Date.now() + 86_400_000),
    });
    expect(await validateLicense("QSB-AAAA-AAAA-AAAA-AAAA")).toBe("active");
  });
});
