// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/db", () => ({
  prisma: {
    user: { findUnique: vi.fn(), update: vi.fn() },
    trialRecord: { update: vi.fn() },
    $transaction: vi.fn(async (ops: unknown[]) =>
      Promise.all(ops.map((op) => op as Promise<unknown>))
    ),
  },
}));

import { prisma } from "@/lib/db";
const mockUserFind = prisma.user.findUnique as unknown as ReturnType<typeof vi.fn>;
const mockTransaction = prisma.$transaction as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => vi.clearAllMocks());

function makeReq(token: string | null) {
  const url = token
    ? `http://localhost/api/auth/verify-email?token=${token}`
    : "http://localhost/api/auth/verify-email";
  return new Request(url) as never;
}

describe("Email verification", () => {
  it("redirects to /login?error=invalid-token when no token", async () => {
    const { GET } = await import("./verify-email/route");
    const res = await GET(makeReq(null));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("invalid-token");
  });

  it("redirects to /login?error=expired-token for unknown token", async () => {
    mockUserFind.mockResolvedValue(null);
    const { GET } = await import("./verify-email/route");
    const res = await GET(makeReq("no-such-token"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("expired-token");
  });

  it("redirects to /login?error=expired-token for expired token", async () => {
    mockUserFind.mockResolvedValue({
      id: "u1",
      email: "a@b.com",
      emailVerified: false,
      verifyToken: "expired-tok",
      verifyTokenExpiry: new Date(Date.now() - 1000),
    });
    const { GET } = await import("./verify-email/route");
    const res = await GET(makeReq("expired-tok"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("expired-token");
  });

  it("verifies email, starts trial, and redirects to /dashboard", async () => {
    mockUserFind.mockResolvedValue({
      id: "u1",
      email: "a@b.com",
      emailVerified: false,
      verifyToken: "valid-token",
      verifyTokenExpiry: new Date(Date.now() + 60_000),
    });
    mockTransaction.mockResolvedValue([{}, {}]);

    const { GET } = await import("./verify-email/route");
    const res = await GET(makeReq("valid-token"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/dashboard");
    expect(mockTransaction).toHaveBeenCalledOnce();
    // Session cookie should be set
    const setCookie = res.headers.get("set-cookie");
    expect(setCookie).toContain("qsb-session");
  });

  it("redirects already-verified users to /dashboard without re-processing", async () => {
    mockUserFind.mockResolvedValue({
      id: "u1",
      email: "a@b.com",
      emailVerified: true,
      verifyToken: "old-token",
      verifyTokenExpiry: new Date(Date.now() + 60_000),
    });
    const { GET } = await import("./verify-email/route");
    const res = await GET(makeReq("old-token"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/dashboard");
    expect(mockTransaction).not.toHaveBeenCalled();
  });
});
