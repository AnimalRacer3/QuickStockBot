import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "sk_test_placeholder", {
  typescript: true,
});

export const STRIPE_PRICE_ID = process.env.STRIPE_PRICE_ID ?? "";
export const TRIAL_PERIOD_DAYS = 30;
