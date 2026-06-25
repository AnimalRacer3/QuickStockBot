import type Stripe from "stripe";
import { prisma } from "./db";

export async function processStripeEvent(event: Stripe.Event): Promise<void> {
  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      if (session.mode !== "subscription") break;
      const userId = session.metadata?.userId;
      if (!userId) break;
      await prisma.user.update({
        where: { id: userId },
        data: {
          stripeCustomerId: session.customer as string,
          subscriptionId: session.subscription as string,
        },
      });
      break;
    }

    case "customer.subscription.created":
    case "customer.subscription.updated": {
      const sub = event.data.object as Stripe.Subscription;
      await prisma.user.update({
        where: { stripeCustomerId: sub.customer as string },
        data: {
          subscriptionId: sub.id,
          subscriptionStatus: sub.status,
          trialEnd: sub.trial_end ? new Date(sub.trial_end * 1000) : null,
          currentPeriodEnd: sub.current_period_end ? new Date(sub.current_period_end * 1000) : null,
        },
      });
      break;
    }

    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      await prisma.user.update({
        where: { stripeCustomerId: sub.customer as string },
        data: {
          subscriptionStatus: "canceled",
          currentPeriodEnd: sub.current_period_end ? new Date(sub.current_period_end * 1000) : null,
        },
      });
      break;
    }

    case "invoice.payment_failed": {
      const invoice = event.data.object as Stripe.Invoice;
      if (!invoice.customer) break;
      await prisma.user.update({
        where: { stripeCustomerId: invoice.customer as string },
        data: { subscriptionStatus: "past_due" },
      });
      break;
    }
  }
}
