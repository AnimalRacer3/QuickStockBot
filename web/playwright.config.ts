import { defineConfig, devices } from "@playwright/test";

// Align test-runner process secret with the webServer env so signSession in
// test files produces cookies the dev server will accept.
process.env.SESSION_SECRET = "test-secret-for-playwright-must-be-32c";

const preinstalledChrome =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ??
  (process.env.PLAYWRIGHT_BROWSERS_PATH
    ? `${process.env.PLAYWRIGHT_BROWSERS_PATH}/chromium_headless_shell-1194/chrome-linux/headless_shell`
    : undefined);

export default defineConfig({
  testMatch: ["**/e2e/**/*.spec.ts", "**/tests/e2e/**/*.spec.ts"],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "line",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    headless: true,
    launchOptions: {
      executablePath: preinstalledChrome,
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    env: {
      NODE_ENV: "test",
      SESSION_SECRET: "test-secret-for-playwright-must-be-32c",
      DATABASE_URL: process.env.DATABASE_URL ?? "postgresql://test:test@localhost:5432/test",
      ENABLE_TEST_HELPERS: "1",
      STRIPE_SECRET_KEY: "sk_test_placeholder",
      STRIPE_PRICE_ID: "price_test_placeholder",
      STRIPE_WEBHOOK_SECRET: "whsec_test_placeholder",
    },
    timeout: 60_000,
  },
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
});
