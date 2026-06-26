import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { prisma } from "@/lib/db";
import { resolveUserTier } from "@/lib/plan";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  const session = token ? await verifySession(token) : null;
  if (!session?.userId) {
    return NextResponse.json({ tier: null }, { status: 401 });
  }

  const user = await prisma.user.findUnique({
    where: { id: session.userId },
    select: { subscriptionStatus: true, subscriptionId: true },
  });

  if (!user) {
    return NextResponse.json({ tier: null }, { status: 404 });
  }

  const tier = await resolveUserTier(user);
  return NextResponse.json({ tier });
}
