// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";
import { processStripeEvent } from "../lib/billing";
import type Stripe from "stripe";

const mockUpdate = vi.fn().mockResolvedValue({});

vi.mock("../lib/db", () => ({
  prisma: {
    user: {
      update: (...args: unknown[]) => mockUpdate(...args),
    },
  },
}));

function makeEvent<T>(type: string, data: T): Stripe.Event {
  return {
    id: "evt_test",
    object: "event",
    type,
    data: { object: data as Stripe.Event.Data["object"] },
    api_version: "2024-12-18.acacia",
    created: Math.floor(Date.now() / 1000),
    livemode: false,
    pending_webhooks: 0,
    request: null,
  } as Stripe.Event;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("processStripeEvent — checkout.session.completed", () => {
  it("links customer and subscription to user on checkout completion", async () => {
    const event = makeEvent("checkout.session.completed", {
      mode: "subscription",
      customer: "cus_123",
      subscription: "sub_abc",
      metadata: { userId: "user_001" },
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { id: "user_001" },
      data: {
        stripeCustomerId: "cus_123",
        subscriptionId: "sub_abc",
      },
    });
  });

  it("ignores non-subscription checkout sessions", async () => {
    const event = makeEvent("checkout.session.completed", {
      mode: "payment",
      customer: "cus_123",
      metadata: { userId: "user_001" },
    });

    await processStripeEvent(event);

    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it("ignores checkout sessions without userId metadata", async () => {
    const event = makeEvent("checkout.session.completed", {
      mode: "subscription",
      customer: "cus_123",
      subscription: "sub_abc",
      metadata: {},
    });

    await processStripeEvent(event);

    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

describe("processStripeEvent — customer.subscription.created", () => {
  it("sets subscription status to trialing when trial starts", async () => {
    const trialEndTs = Math.floor(Date.now() / 1000) + 30 * 86400;
    const periodEndTs = trialEndTs;
    const event = makeEvent("customer.subscription.created", {
      id: "sub_abc",
      customer: "cus_123",
      status: "trialing",
      trial_end: trialEndTs,
      current_period_end: periodEndTs,
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { stripeCustomerId: "cus_123" },
      data: {
        subscriptionId: "sub_abc",
        subscriptionStatus: "trialing",
        trialEnd: new Date(trialEndTs * 1000),
        currentPeriodEnd: new Date(periodEndTs * 1000),
      },
    });
  });

  it("sets subscription status to active for non-trial subscription", async () => {
    const periodEndTs = Math.floor(Date.now() / 1000) + 30 * 86400;
    const event = makeEvent("customer.subscription.created", {
      id: "sub_abc",
      customer: "cus_123",
      status: "active",
      trial_end: null,
      current_period_end: periodEndTs,
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { stripeCustomerId: "cus_123" },
      data: {
        subscriptionId: "sub_abc",
        subscriptionStatus: "active",
        trialEnd: null,
        currentPeriodEnd: new Date(periodEndTs * 1000),
      },
    });
  });
});

describe("processStripeEvent — customer.subscription.updated", () => {
  it("transitions status from trialing to active when trial ends", async () => {
    const periodEndTs = Math.floor(Date.now() / 1000) + 30 * 86400;
    const event = makeEvent("customer.subscription.updated", {
      id: "sub_abc",
      customer: "cus_123",
      status: "active",
      trial_end: null,
      current_period_end: periodEndTs,
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { stripeCustomerId: "cus_123" },
      data: {
        subscriptionId: "sub_abc",
        subscriptionStatus: "active",
        trialEnd: null,
        currentPeriodEnd: new Date(periodEndTs * 1000),
      },
    });
  });

  it("sets status to past_due on payment failure update", async () => {
    const periodEndTs = Math.floor(Date.now() / 1000) + 30 * 86400;
    const event = makeEvent("customer.subscription.updated", {
      id: "sub_abc",
      customer: "cus_123",
      status: "past_due",
      trial_end: null,
      current_period_end: periodEndTs,
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { stripeCustomerId: "cus_123" },
      data: {
        subscriptionId: "sub_abc",
        subscriptionStatus: "past_due",
        trialEnd: null,
        currentPeriodEnd: new Date(periodEndTs * 1000),
      },
    });
  });
});

describe("processStripeEvent — customer.subscription.deleted", () => {
  it("sets status to canceled when subscription is deleted", async () => {
    const periodEndTs = Math.floor(Date.now() / 1000) + 5 * 86400;
    const event = makeEvent("customer.subscription.deleted", {
      id: "sub_abc",
      customer: "cus_123",
      status: "canceled",
      trial_end: null,
      current_period_end: periodEndTs,
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { stripeCustomerId: "cus_123" },
      data: {
        subscriptionStatus: "canceled",
        currentPeriodEnd: new Date(periodEndTs * 1000),
      },
    });
  });
});

describe("processStripeEvent — invoice.payment_failed", () => {
  it("sets status to past_due on payment failure", async () => {
    const event = makeEvent("invoice.payment_failed", {
      id: "in_123",
      customer: "cus_123",
      subscription: "sub_abc",
    });

    await processStripeEvent(event);

    expect(mockUpdate).toHaveBeenCalledWith({
      where: { stripeCustomerId: "cus_123" },
      data: { subscriptionStatus: "past_due" },
    });
  });

  it("ignores invoice events without customer", async () => {
    const event = makeEvent("invoice.payment_failed", {
      id: "in_123",
      customer: null,
    });

    await processStripeEvent(event);

    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

describe("processStripeEvent — unknown events", () => {
  it("silently ignores unhandled event types", async () => {
    const event = makeEvent("charge.succeeded", { id: "ch_123" });
    await expect(processStripeEvent(event)).resolves.not.toThrow();
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});
