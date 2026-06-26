import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "sk_test_placeholder", {
  typescript: true,
});

export const STRIPE_PRICE_ID_PREMIUM = process.env.STRIPE_PRICE_ID_PREMIUM ?? "";
export const STRIPE_PRICE_ID_BASIC = process.env.STRIPE_PRICE_ID_BASIC ?? "";

/** Backward-compat alias — points at the premium price. */
export const STRIPE_PRICE_ID = STRIPE_PRICE_ID_PREMIUM;

export const TRIAL_PERIOD_DAYS = 30;

/**
 * Throws a descriptive error if priceId is empty or not a real Stripe price ID.
 * Prevents placeholder strings like "price_id" from silently reaching Stripe.
 */
export function assertPriceId(priceId: string, label: string): void {
  if (!priceId || !priceId.startsWith("price_")) {
    throw new Error(
      `${label} is not a valid Stripe price ID (got: "${priceId || "(empty)"}"). ` +
        `Set it to a real value starting with "price_".`
    );
  }
}
