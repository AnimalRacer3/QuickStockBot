import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

function toDate(val: number | string | null | undefined): Date | null {
  if (val == null) return null;
  if (typeof val === "number") return new Date(val * 1000);
  return new Date(val);
}

export async function POST(request: NextRequest) {
  if (process.env.ENABLE_TEST_HELPERS !== "1") {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const body = (await request.json()) as {
    email: string;
    subscriptionStatus: string | null;
    trialEnd?: number | string | null;
    currentPeriodEnd?: number | string | null;
    stripeCustomerId?: string;
    subscriptionId?: string;
  };

  const user = await prisma.user.findUnique({ where: { email: body.email } });
  if (!user) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  await prisma.user.update({
    where: { id: user.id },
    data: {
      subscriptionStatus: body.subscriptionStatus,
      trialEnd: toDate(body.trialEnd),
      currentPeriodEnd: toDate(body.currentPeriodEnd),
      stripeCustomerId: body.stripeCustomerId,
      subscriptionId: body.subscriptionId,
    },
  });

  return NextResponse.json({ ok: true });
}
