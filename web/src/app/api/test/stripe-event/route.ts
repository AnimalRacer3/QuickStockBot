import { NextRequest, NextResponse } from "next/server";
import { processStripeEvent } from "@/lib/billing";
import type Stripe from "stripe";

export async function POST(request: NextRequest) {
  if (process.env.ENABLE_TEST_HELPERS !== "1") {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const event = (await request.json()) as Stripe.Event;

  try {
    await processStripeEvent(event);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  return NextResponse.json({ received: true });
}
