import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import {
  verifyPassword,
  signSession,
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  getClientIp,
} from "@/lib/auth";
import { checkRateLimit } from "@/lib/rate-limit";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const { email, password } = body as { email?: string; password?: string };

  if (!email || !password) {
    return NextResponse.json({ error: "Email and password required" }, { status: 400 });
  }

  // 10 login attempts per IP per minute
  const clientIp = getClientIp(req);
  if (!checkRateLimit(`login:${clientIp}`, 10, 10 / 60)) {
    return NextResponse.json({ error: "Too many requests" }, { status: 429 });
  }

  const user = await prisma.user.findUnique({ where: { email } });
  if (!user || !(await verifyPassword(user.passwordHash, password))) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  }

  const jwt = await signSession({
    userId: user.id,
    email: user.email,
    emailVerified: user.emailVerified,
  });

  const res = NextResponse.json({
    success: true,
    emailVerified: user.emailVerified,
  });
  res.cookies.set(SESSION_COOKIE, jwt, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: SESSION_TTL_SECONDS,
    path: "/",
  });
  return res;
}
