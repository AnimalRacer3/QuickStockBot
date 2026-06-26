import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getBaseUrl } from "@/lib/url";

export async function GET(req: NextRequest) {
  const token = new URL(req.url).searchParams.get("token");

  if (!token) {
    return NextResponse.redirect(new URL("/login?error=invalid-token", getBaseUrl()));
  }

  const user = await prisma.user.findUnique({ where: { verifyToken: token } });

  if (!user || !user.verifyTokenExpiry || user.verifyTokenExpiry < new Date()) {
    return NextResponse.redirect(new URL("/login?error=expired-token", getBaseUrl()));
  }

  if (user.emailVerified) {
    // Already verified; redirect to login so the user authenticates themselves.
    return NextResponse.redirect(new URL("/login?verified=1", getBaseUrl()));
  }

  // Access is gated on subscriptionStatus written by Stripe webhooks, not on
  // trialRecord. The trialRecord (created at signup) is kept only for IP-based
  // trial deduplication; we do not set trial dates here.
  await prisma.user.update({
    where: { id: user.id },
    data: { emailVerified: true, verifyToken: null, verifyTokenExpiry: null },
  });

  // Do not set a session cookie — the user must log in themselves.
  return NextResponse.redirect(new URL("/login?verified=1", getBaseUrl()));
}
