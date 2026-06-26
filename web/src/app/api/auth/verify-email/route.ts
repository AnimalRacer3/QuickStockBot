import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

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
    // Already verified; redirect to login so the user authenticates themselves.
    return NextResponse.redirect(new URL("/login?verified=1", BASE_URL));
  }

  // Access is gated on subscriptionStatus written by Stripe webhooks, not on
  // trialRecord. The trialRecord (created at signup) is kept only for IP-based
  // trial deduplication; we do not set trial dates here.
  await prisma.user.update({
    where: { id: user.id },
    data: { emailVerified: true, verifyToken: null, verifyTokenExpiry: null },
  });

  // Do not set a session cookie — the user must log in themselves.
  return NextResponse.redirect(new URL("/login?verified=1", BASE_URL));
}
