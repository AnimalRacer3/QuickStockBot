/**
 * Playwright E2E auth tests.
 *
 * Route-protection tests (no database needed — middleware only checks cookies).
 * Auth-flow tests mock API responses with page.route() and use a test session
 * endpoint to set verified/unverified cookies without a real database.
 *
 * Run with: npm run test:e2e
 * Requires a running Next.js server (configured via playwright.config.ts).
 */
import { test, expect } from "@playwright/test";
import { SESSION_COOKIE, signSession } from "../../src/lib/session";

// ─── Route protection ─────────────────────────────────────────────────────────

test("unauthenticated user is redirected from /dashboard to /login", async ({
  page,
}) => {
  await page.context().clearCookies();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("unauthenticated user is redirected from /view to /login", async ({
  page,
}) => {
  await page.context().clearCookies();
  await page.goto("/view");
  await expect(page).toHaveURL(/\/login/);
});

test("user with unverified email is redirected from /dashboard to /verify-email", async ({
  page,
}) => {
  const token = await signSession({
    userId: "test-user",
    email: "test@example.com",
    emailVerified: false,
  });
  await page.context().addCookies([
    {
      name: SESSION_COOKIE,
      value: token,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/verify-email/);
});

test("verified user can access /dashboard", async ({ page }) => {
  const token = await signSession({
    userId: "test-user",
    email: "test@example.com",
    emailVerified: true,
  });
  await page.context().addCookies([
    {
      name: SESSION_COOKIE,
      value: token,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.locator("h1")).toContainText("Dashboard");
});

// ─── Sign-up → verify → dashboard flow ───────────────────────────────────────

test("sign up form → check email page", async ({ page }) => {
  let capturedToken: string | null = null;

  // Mock signup API so no database is needed
  await page.route("/api/auth/signup", async (route) => {
    capturedToken = "mock-verify-token";
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ success: true, verifyToken: capturedToken }),
    });
  });

  await page.goto("/signup");
  await page.fill('input[type="email"]', "newuser@example.com");
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL(/\/verify-email/);
  await expect(page.locator("h1")).toContainText("Check your email");
  expect(capturedToken).toBe("mock-verify-token");
});

test("duplicate email signup shows error", async ({ page }) => {
  await page.route("/api/auth/signup", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ error: "Email already registered" }),
    });
  });

  await page.goto("/signup");
  await page.fill('input[type="email"]', "existing@example.com");
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');

  await expect(page.locator('[role="alert"]')).toContainText(
    "Email already registered"
  );
});

test("login with unverified account redirects to /verify-email", async ({
  page,
}) => {
  await page.route("/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, emailVerified: false }),
    });
  });

  await page.goto("/login");
  await page.fill('input[type="email"]', "unverified@example.com");
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL(/\/verify-email/);
});

test("login with verified account redirects to /dashboard", async ({ page }) => {
  const token = await signSession({
    userId: "u1",
    email: "verified@example.com",
    emailVerified: true,
  });

  await page.route("/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "set-cookie": `${SESSION_COOKIE}=${token}; Path=/; HttpOnly` },
      body: JSON.stringify({ success: true, emailVerified: true }),
    });
  });

  await page.goto("/login");
  await page.fill('input[type="email"]', "verified@example.com");
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL(/\/dashboard/);
});
