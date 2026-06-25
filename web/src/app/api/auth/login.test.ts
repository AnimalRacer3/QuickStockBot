// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";
import { hashPassword } from "@/lib/auth";

vi.mock("@/lib/db", () => ({
  prisma: {
    user: { findUnique: vi.fn() },
  },
}));

import { prisma } from "@/lib/db";
const mockFindUnique = prisma.user.findUnique as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => vi.clearAllMocks());

describe("Login", () => {
  it("returns 400 for missing credentials", async () => {
    const { POST } = await import("./login/route");
    const res = await POST(
      new Request("http://localhost/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }) as never
    );
    expect(res.status).toBe(400);
  });

  it("returns 401 for unknown email", async () => {
    mockFindUnique.mockResolvedValue(null);
    const { POST } = await import("./login/route");
    const res = await POST(
      new Request("http://localhost/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "nobody@example.com", password: "password123" }),
      }) as never
    );
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toMatch(/invalid credentials/i);
  });

  it("returns 401 for wrong password", async () => {
    const hash = await hashPassword("correct-password");
    mockFindUnique.mockResolvedValue({
      id: "u1",
      email: "user@example.com",
      passwordHash: hash,
      emailVerified: true,
    });
    const { POST } = await import("./login/route");
    const res = await POST(
      new Request("http://localhost/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "user@example.com", password: "wrong-password" }),
      }) as never
    );
    expect(res.status).toBe(401);
  });

  it("returns 200 and sets session cookie on valid credentials", async () => {
    const hash = await hashPassword("mypassword");
    mockFindUnique.mockResolvedValue({
      id: "u1",
      email: "user@example.com",
      passwordHash: hash,
      emailVerified: true,
    });
    const { POST } = await import("./login/route");
    const res = await POST(
      new Request("http://localhost/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "user@example.com", password: "mypassword" }),
      }) as never
    );
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.emailVerified).toBe(true);
    const setCookie = res.headers.get("set-cookie");
    expect(setCookie).toContain("qsb-session");
  });

  it("sets emailVerified: false for unverified users", async () => {
    const hash = await hashPassword("password");
    mockFindUnique.mockResolvedValue({
      id: "u2",
      email: "unverified@example.com",
      passwordHash: hash,
      emailVerified: false,
    });
    const { POST } = await import("./login/route");
    const res = await POST(
      new Request("http://localhost/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "unverified@example.com", password: "password" }),
      }) as never
    );
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.emailVerified).toBe(false);
  });
});
