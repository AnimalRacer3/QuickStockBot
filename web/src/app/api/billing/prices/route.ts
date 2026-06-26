import { NextResponse } from "next/server";
import { stripe, STRIPE_PRICE_ID_BASIC, STRIPE_PRICE_ID_PREMIUM } from "@/lib/stripe";
import type Stripe from "stripe";

function formatPrice(price: Stripe.Price): string | null {
  if (!price.unit_amount) return null;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: price.currency,
  }).format(price.unit_amount / 100);
}

async function safeRetrieve(priceId: string): Promise<string | null> {
  if (!priceId || !priceId.startsWith("price_")) return null;
  try {
    const price = await stripe.prices.retrieve(priceId);
    return formatPrice(price);
  } catch {
    return null;
  }
}

export async function GET() {
  const [basic, premium] = await Promise.all([
    safeRetrieve(STRIPE_PRICE_ID_BASIC),
    safeRetrieve(STRIPE_PRICE_ID_PREMIUM),
  ]);

  return NextResponse.json({ basic, premium });
}
