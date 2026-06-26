import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { stripe, STRIPE_PRICE_ID_PREMIUM, STRIPE_PRICE_ID_BASIC, TRIAL_PERIOD_DAYS } from "@/lib/stripe";
import { prisma } from "@/lib/db";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  const session = token ? await verifySession(token) : null;
  if (!session?.userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json().catch(() => ({}))) as {
    trial?: boolean;
    plan?: "basic" | "premium";
  };
  const trial = body.trial === true;
  // Trial always uses premium; paid checkout uses whichever plan the user chose (default premium)
  const plan = trial ? "premium" : (body.plan ?? "premium");
  const priceId = plan === "basic" ? STRIPE_PRICE_ID_BASIC : STRIPE_PRICE_ID_PREMIUM;

  if (!priceId) {
    const label = plan === "basic" ? "STRIPE_PRICE_ID_BASIC" : "STRIPE_PRICE_ID_PREMIUM";
    return NextResponse.json(
      { error: `Billing is not configured (missing ${label})` },
      { status: 500 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id: session.userId },
    select: { id: true, email: true, stripeCustomerId: true },
  });
  if (!user) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";

  try {
    const checkoutSession = await stripe.checkout.sessions.create({
      mode: "subscription",
      payment_method_types: ["card"],
      customer_email: user.stripeCustomerId ? undefined : user.email,
      customer: user.stripeCustomerId ?? undefined,
      line_items: [{ price: priceId, quantity: 1 }],
      subscription_data: {
        ...(trial ? { trial_period_days: TRIAL_PERIOD_DAYS } : {}),
        metadata: { userId: user.id },
      },
      metadata: { userId: user.id },
      success_url: `${baseUrl}/dashboard?checkout=success`,
      cancel_url: `${baseUrl}/billing?checkout=canceled`,
    });

    return NextResponse.json({ url: checkoutSession.url });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Stripe error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
