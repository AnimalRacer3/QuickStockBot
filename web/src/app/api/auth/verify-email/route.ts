import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { signSession, SESSION_COOKIE, SESSION_TTL_SECONDS } from "@/lib/auth";

const BASE_URL = process.env.NEXTAUTH_URL || "http://localhost:3000";

export async function GET(req: NextRequest) {
  const token = new URL(req.url).searchParams.get("token");

  if (!token) {
    return NextResponse.redirect(new URL("/login?error=invalid-token", BASE_URL));
  }

  const user = await prisma.user.findUnique({ where: { verifyToken: token } });

  if (!user || !user.verifyTokenExpiry || user.verifyTokenExpiry < new Date()) {
    return NextResponse.redirect(new URL("/login?error=expired-token", BASE_URL));
  }

  if (user.emailVerified) {
    return NextResponse.redirect(new URL("/dashboard", BASE_URL));
  }

  const trialStart = new Date();
  const trialEnd = new Date(trialStart);
  trialEnd.setMonth(trialEnd.getMonth() + 1);

  await prisma.$transaction([
    prisma.user.update({
      where: { id: user.id },
      data: { emailVerified: true, verifyToken: null, verifyTokenExpiry: null },
    }),
    prisma.trialRecord.update({
      where: { userId: user.id },
      data: { trialStart, trialEnd },
    }),
  ]);

  const jwt = await signSession({
    userId: user.id,
    email: user.email,
    emailVerified: true,
  });

  const res = NextResponse.redirect(new URL("/dashboard", BASE_URL));
  res.cookies.set(SESSION_COOKIE, jwt, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: SESSION_TTL_SECONDS,
    path: "/",
  });
  return res;
}
