import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders the hero headline and primary CTA", async ({ page }) => {
    await expect(page.locator("h1")).toBeVisible();
    const heroCta = page.getByRole("link", { name: /start 1 month free/i });
    await expect(heroCta).toBeVisible();
    await expect(heroCta).toHaveAttribute("href", "/signup");
  });

  test("pricing section shows $6.99 and free trial badge", async ({ page }) => {
    await page.locator("#pricing").scrollIntoViewIfNeeded();
    await expect(page.getByText("$6.99")).toBeVisible();
    await expect(page.getByText(/1 month free/i).first()).toBeVisible();
  });

  test("pricing CTA links to /signup", async ({ page }) => {
    await page.locator("#pricing").scrollIntoViewIfNeeded();
    const pricingCta = page.getByRole("link", { name: /start free trial/i });
    await expect(pricingCta).toBeVisible();
    await expect(pricingCta).toHaveAttribute("href", "/signup");
  });

  test("nav contains Log in and Start free links", async ({ page }) => {
    await expect(page.getByRole("link", { name: /log in/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /start free/i }).first()).toBeVisible();
  });

  test("how-it-works section is present", async ({ page }) => {
    await page.locator("#how-it-works").scrollIntoViewIfNeeded();
    await expect(
      page.getByRole("heading", { name: /from setup to live trading/i }),
    ).toBeVisible();
  });

  test("features section is present", async ({ page }) => {
    await page.locator("#features").scrollIntoViewIfNeeded();
    await expect(
      page.getByRole("heading", { name: /built for serious traders/i }),
    ).toBeVisible();
  });

  test("page is responsive at mobile width", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    // Hero and pricing CTA should both be visible at mobile
    await expect(page.locator("h1")).toBeVisible();
    await page.locator("#pricing").scrollIntoViewIfNeeded();
    await expect(page.getByText("$6.99")).toBeVisible();
  });
});
