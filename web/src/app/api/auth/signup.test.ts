// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock database and email before imports
vi.mock("@/lib/db", () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
    },
    trialRecord: {
      findFirst: vi.fn(),
      update: vi.fn(),
    },
    $transaction: vi.fn(),
  },
}));

vi.mock("@/lib/email", () => ({
  sendVerificationEmail: vi.fn().mockResolvedValue(undefined),
}));

import { prisma } from "@/lib/db";
import { sendVerificationEmail } from "@/lib/email";

// Helpers to cast mocked fns
const db = {
  user: prisma.user as unknown as Record<string, ReturnType<typeof vi.fn>>,
  trialRecord: prisma.trialRecord as unknown as Record<string, ReturnType<typeof vi.fn>>,
  $transaction: prisma.$transaction as unknown as ReturnType<typeof vi.fn>,
};

beforeEach(() => vi.clearAllMocks());

// ─── Signup validation ────────────────────────────────────────────────────────

describe("Signup: input validation", () => {
  it("rejects missing email", async () => {
    const { POST } = await import("./signup/route");
    const req = new Request("http://localhost/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: "password123" }),
    });
    const res = await POST(req as never);
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toMatch(/email/i);
  });

  it("rejects short password", async () => {
    db.user.findUnique.mockResolvedValue(null);
    db.trialRecord.findFirst.mockResolvedValue(null);
    const { POST } = await import("./signup/route");
    const req = new Request("http://localhost/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "a@b.com", password: "short" }),
    });
    const res = await POST(req as never);
    expect(res.status).toBe(400);
  });
});

// ─── Duplicate email ──────────────────────────────────────────────────────────

describe("Signup: duplicate email is blocked", () => {
  it("returns 409 when email already exists", async () => {
    db.user.findUnique.mockResolvedValue({ id: "u1", email: "dup@example.com" });
    const { POST } = await import("./signup/route");
    const req = new Request("http://localhost/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "dup@example.com", password: "password123" }),
    });
    const res = await POST(req as never);
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.error).toMatch(/already registered/i);
  });
});

// ─── Repeat IP ────────────────────────────────────────────────────────────────

describe("Signup: repeat IP is denied", () => {
  it("returns 409 when IP already has a trial record", async () => {
    db.user.findUnique.mockResolvedValue(null);
    db.trialRecord.findFirst.mockResolvedValue({ id: "t1", signupIp: "1.2.3.4" });
    const { POST } = await import("./signup/route");
    const req = new Request("http://localhost/api/auth/signup", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-forwarded-for": "1.2.3.4",
      },
      body: JSON.stringify({ email: "new@example.com", password: "password123" }),
    });
    const res = await POST(req as never);
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.error).toMatch(/trial/i);
  });
});

// ─── Successful signup ────────────────────────────────────────────────────────

describe("Signup: success path", () => {
  it("creates user, sends verification email, returns 201", async () => {
    db.user.findUnique.mockResolvedValue(null);
    db.trialRecord.findFirst.mockResolvedValue(null);
    db.user.create.mockResolvedValue({
      id: "u1",
      email: "new@example.com",
    });

    const { POST } = await import("./signup/route");
    const req = new Request("http://localhost/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "new@example.com", password: "password123" }),
    });
    const res = await POST(req as never);
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(sendVerificationEmail).toHaveBeenCalledOnce();
  });
});
