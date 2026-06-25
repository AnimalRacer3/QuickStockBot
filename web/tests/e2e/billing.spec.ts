import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

const BASE = "http://localhost:3000";
const TEST_EMAIL = "billing-e2e@example.com";
const TEST_PASSWORD = "testpassword123";

async function createTestUser(request: APIRequestContext) {
  const res = await request.post(`${BASE}/api/test/create-user`, {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
}

async function setSubscription(
  request: APIRequestContext,
  status: string | null,
  extras: Record<string, unknown> = {},
) {
  const res = await request.post(`${BASE}/api/test/set-subscription`, {
    data: { email: TEST_EMAIL, subscriptionStatus: status, ...extras },
  });
  expect(res.ok()).toBeTruthy();
}

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', TEST_EMAIL);
  await page.fill('input[type="password"]', TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 15_000 });
}

// ─── Gating: unauthenticated ───────────────────────────────────────────────

test("unauthenticated user is redirected to login from dashboard", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("unauthenticated user is redirected to login from billing", async ({ page }) => {
  await page.goto("/billing");
  await expect(page).toHaveURL(/\/login/);
});

// ─── Gating: no subscription ──────────────────────────────────────────────

test("user with no subscription is redirected to /billing from dashboard", async ({
  page,
  request,
}) => {
  await createTestUser(request);
  await login(page);
  await page.waitForURL(/\/(billing|dashboard)/);
  await expect(page).toHaveURL(/\/billing/);
});

// ─── Checkout → status active → dashboard accessible ──────────────────────

test("simulated checkout sets status to trialing and grants dashboard access", async ({
  page,
  request,
}) => {
  await createTestUser(request);

  const trialEnd = Math.floor(Date.now() / 1000) + 30 * 86400;
  const periodEnd = trialEnd;

  await setSubscription(request, "trialing", {
    stripeCustomerId: "cus_test_123",
    subscriptionId: "sub_test_abc",
    trialEnd,
    currentPeriodEnd: periodEnd,
  });

  await login(page);
  await page.waitForURL(/\/(billing|dashboard)/);
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.locator("h1")).toContainText("Dashboard");
  await expect(page.getByText("Free Trial")).toBeVisible();
});

test("active subscription grants dashboard access", async ({ page, request }) => {
  await createTestUser(request);
  const periodEnd = Math.floor(Date.now() / 1000) + 30 * 86400;
  await setSubscription(request, "active", {
    stripeCustomerId: "cus_test_123",
    subscriptionId: "sub_test_abc",
    currentPeriodEnd: periodEnd,
  });

  await login(page);
  await page.waitForURL(/\/(billing|dashboard)/);
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByText("Active")).toBeVisible();
});

// ─── Cancellation → access revoked ───────────────────────────────────────

test("canceled subscription blocks dashboard access and shows billing page", async ({
  page,
  request,
}) => {
  await createTestUser(request);
  const periodEnd = Math.floor(Date.now() / 1000) - 86400;
  await setSubscription(request, "canceled", {
    stripeCustomerId: "cus_test_123",
    subscriptionId: "sub_test_abc",
    currentPeriodEnd: periodEnd,
  });

  await login(page);
  await expect(page).toHaveURL(/\/billing/);
  await expect(page.getByText("Canceled", { exact: true })).toBeVisible();
  await expect(page.getByText("Start free trial")).toBeVisible();
});

test("navigating to /dashboard after cancel redirects to /billing", async ({ page, request }) => {
  await createTestUser(request);
  await setSubscription(request, "canceled", { stripeCustomerId: "cus_test_123" });

  await login(page);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/billing/);
});

// ─── Payment failed → access blocked ─────────────────────────────────────

test("past_due subscription blocks dashboard access", async ({ page, request }) => {
  await createTestUser(request);
  await setSubscription(request, "past_due", { stripeCustomerId: "cus_test_123" });

  await login(page);
  await page.waitForURL(/\/(billing|dashboard)/);
  await expect(page).toHaveURL(/\/billing/);
  await expect(page.getByText("Payment Past Due")).toBeVisible();
});

// ─── Billing page shows correct state ─────────────────────────────────────

test("billing page shows trial info and manage subscription link", async ({ page, request }) => {
  await createTestUser(request);
  const trialEnd = Math.floor(Date.now() / 1000) + 15 * 86400;
  await setSubscription(request, "trialing", {
    stripeCustomerId: "cus_test_123",
    subscriptionId: "sub_test_abc",
    trialEnd,
  });

  await login(page);
  await page.goto("/billing");
  await page.waitForURL(/\/billing/, { timeout: 10_000 });
  await expect(page.getByText("Free Trial", { exact: true })).toBeVisible();
  await expect(page.getByText("Manage subscription")).toBeVisible();
});

// ─── Webhook event processing via test endpoint ───────────────────────────

test("stripe-event endpoint updates subscription status", async ({ page, request }) => {
  await createTestUser(request);
  await setSubscription(request, "trialing", {
    stripeCustomerId: "cus_webhook_test",
    subscriptionId: "sub_webhook_test",
  });

  const cancelEvent = {
    id: "evt_test_cancel",
    object: "event",
    type: "customer.subscription.deleted",
    created: Math.floor(Date.now() / 1000),
    livemode: false,
    pending_webhooks: 0,
    request: null,
    api_version: "2024-12-18.acacia",
    data: {
      object: {
        id: "sub_webhook_test",
        object: "subscription",
        customer: "cus_webhook_test",
        status: "canceled",
        trial_end: null,
        current_period_end: Math.floor(Date.now() / 1000) + 86400,
      },
    },
  };

  const res = await request.post(`${BASE}/api/test/stripe-event`, {
    data: cancelEvent,
    headers: { "Content-Type": "application/json" },
  });
  expect(res.ok()).toBeTruthy();

  await login(page);
  await expect(page).toHaveURL(/\/billing/);
  await expect(page.getByText("Canceled", { exact: true })).toBeVisible();
});
