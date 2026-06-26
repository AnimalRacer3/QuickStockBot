import { stripe, STRIPE_PRICE_ID_PREMIUM, STRIPE_PRICE_ID_BASIC } from "./stripe";

export type Tier = "basic" | "premium" | null;

/**
 * Resolves a user's plan tier from their subscription data.
 *
 * - trialing → always "premium"
 * - active subscription → look up price ID from Stripe to determine plan
 * - anything else (no sub, canceled, etc.) → null
 */
export async function resolveUserTier(user: {
  subscriptionStatus: string | null | undefined;
  subscriptionId: string | null | undefined;
}): Promise<Tier> {
  if (user.subscriptionStatus === "trialing") return "premium";

  if (!user.subscriptionId || user.subscriptionStatus !== "active") return null;

  try {
    const subscription = await stripe.subscriptions.retrieve(user.subscriptionId, {
      expand: ["items.data.price"],
    });
    const priceId = subscription.items.data[0]?.price?.id;
    if (STRIPE_PRICE_ID_PREMIUM && priceId === STRIPE_PRICE_ID_PREMIUM) return "premium";
    if (STRIPE_PRICE_ID_BASIC && priceId === STRIPE_PRICE_ID_BASIC) return "basic";
  } catch {
    // If Stripe lookup fails, fall through to null
  }

  return null;
}
