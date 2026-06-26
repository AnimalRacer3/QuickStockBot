import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "sk_test_placeholder", {
  typescript: true,
});

export const STRIPE_PRICE_ID_PREMIUM = process.env.STRIPE_PRICE_ID_PREMIUM ?? "";
export const STRIPE_PRICE_ID_BASIC = process.env.STRIPE_PRICE_ID_BASIC ?? "";
export const TRIAL_PERIOD_DAYS = 30;
