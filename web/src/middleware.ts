import { NextRequest, NextResponse } from "next/server";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { prisma } from "@/lib/db";
import { isAccessAllowed } from "@/lib/subscription";

const PROTECTED = ["/dashboard", "/view"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isProtected = PROTECTED.some((p) => pathname.startsWith(p));
  if (!isProtected) return NextResponse.next();

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  const session = await verifySession(token);
  if (!session) {
    const res = NextResponse.redirect(new URL("/login", req.url));
    res.cookies.delete(SESSION_COOKIE);
    return res;
  }

  if (!session.emailVerified) {
    return NextResponse.redirect(new URL("/verify-email", req.url));
  }

  if (pathname.startsWith("/dashboard")) {
    const user = await prisma.user.findUnique({
      where: { id: session.userId },
      select: { subscriptionStatus: true },
    });
    if (!isAccessAllowed(user?.subscriptionStatus)) {
      return NextResponse.redirect(new URL("/billing", req.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/view/:path*"],
};
