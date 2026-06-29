import { test, expect, type Page } from "@playwright/test";
import { RELAY_URL, RELAY_PASSWORD } from "./mock-relay";

async function connect(page: Page) {
  await page.goto("/connect");
  await page.getByLabel("Relay URL").fill(RELAY_URL);
  await page.getByLabel("Connection Password").fill(RELAY_PASSWORD);
  await page.getByRole("button", { name: "Connect" }).click();
  await page.waitForURL("**/live", { timeout: 10_000 });
}

async function waitForConnected(page: Page) {
  // After a hard navigation, auto-reconnect fires from localStorage.
  // Wait until the nav shows "Connected" (exact match to avoid "Mock relay connected…" log).
  await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15_000 });
}

test.describe("Dashboard e2e", () => {
  test("connect page → live logs", async ({ page }) => {
    await connect(page);
    await expect(page).toHaveURL(/\/live/);
    await waitForConnected(page);
    const logRegion = page.getByRole("log");
    await expect(logRegion).toBeVisible();
    await expect(page.getByRole("log").getByText(/scanner idle/i).first()).toBeVisible({ timeout: 8000 });
  });

  test("active tickers page — shows columns including unknown float", async ({ page }) => {
    await connect(page);
    // Use client-side nav via the nav link to preserve React state
    await page.getByRole("link", { name: "Active Tickers" }).click();
    await page.waitForURL("**/tickers", { timeout: 5000 });
    await expect(page.getByText("AAPL")).toBeVisible({ timeout: 8000 });
    await expect(page.getByText("RVOL")).toBeVisible();
    await expect(page.getByTestId("unknown-float-badge")).toBeVisible();
    // Click AAPL to go to detail
    await page.getByRole("link", { name: "AAPL" }).click();
    await page.waitForURL("**/tickers/AAPL", { timeout: 5000 });
    await expect(page.getByText("High of Day")).toBeVisible();
    await expect(page.getByText("MACD Favorability")).toBeVisible();
  });

  test("settings page — toggle exit_mode to trail_off and save", async ({ page }) => {
    await connect(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await page.waitForURL("**/settings", { timeout: 5000 });
    // Wait for settings to load from relay
    await expect(page.getByText("Exit Mode")).toBeVisible({ timeout: 10000 });
    // Trail Off fields should be hidden initially
    await expect(page.getByText("Trail Off Trigger")).not.toBeVisible();
    // Select trail_off radio — the label wraps the input, so click the label text
    await page.locator("label", { hasText: /^Trail Off$/ }).click();
    await expect(page.getByText("Trail Off Trigger")).toBeVisible();
    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByText("Settings saved.")).toBeVisible({ timeout: 5000 });
  });

  test("settings page — risk override: invalid value blocked, valid accepted", async ({ page }) => {
    await connect(page);
    await page.getByRole("link", { name: "Settings" }).click();
    await page.waitForURL("**/settings", { timeout: 5000 });
    await expect(page.getByText("Risk & Daily Limits")).toBeVisible({ timeout: 10000 });

    // Enable override via the checkbox label
    await page.locator("label", { hasText: "Override risk per trade" }).click();
    const riskInput = page.getByLabel("Risk per trade percent");
    await expect(riskInput).toBeEnabled({ timeout: 3000 });

    // Enter invalid value (>= daily_profit_target_pct of 5.0)
    await riskInput.fill("5.0");
    await riskInput.dispatchEvent("change");
    // The risk error alert — use the specific error text, not the Next.js route announcer
    const riskAlert = page.locator("[role=alert]", { hasText: /Must be less than daily target/ });
    await expect(riskAlert).toBeVisible({ timeout: 3000 });
    await expect(page.getByRole("button", { name: "Save Settings" })).toBeDisabled();

    // Enter valid value (< 5.0)
    await riskInput.fill("1.5");
    await riskInput.dispatchEvent("change");
    await expect(riskAlert).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Save Settings" })).toBeEnabled();
    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByText("Settings saved.")).toBeVisible({ timeout: 5000 });
  });

  test("calendar page — navigate months, click a day", async ({ page }) => {
    await connect(page);
    await page.getByRole("link", { name: "Calendar" }).click();
    await page.waitForURL("**/calendar", { timeout: 5000 });
    // Navigation buttons should be visible
    await expect(page.getByLabel("Previous month")).toBeVisible({ timeout: 8000 });
    await expect(page.getByLabel("Next month")).toBeVisible();

    // Navigate back to March 2024 (from current date June 2026 that's ~27 months back)
    // We'll click prev until we see "March 2024" or give up after 30 clicks
    for (let i = 0; i < 30; i++) {
      const hasMarch = await page.locator("text=March 2024").isVisible();
      if (hasMarch) break;
      await page.getByLabel("Previous month").click();
    }

    await expect(page.locator("text=March 2024")).toBeVisible({ timeout: 5000 });

    // The profit day (March 5) should be green
    const profitDay = page.getByTestId("calendar-day-2024-03-05");
    await expect(profitDay).toBeVisible();
    await profitDay.click();
    // Should show day trades panel
    await expect(page.getByText("2024-03-05")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("AAPL").first()).toBeVisible({ timeout: 5000 });
  });

  test("trade history page — filter by ticker", async ({ page }) => {
    await connect(page);
    await page.getByRole("link", { name: "Trade History" }).click();
    await page.waitForURL("**/history", { timeout: 5000 });
    await expect(page.getByText("AAPL").first()).toBeVisible({ timeout: 8000 });
    // Filter by MEME
    await page.getByPlaceholder("Filter by ticker…").fill("MEME");
    await expect(page.locator("td", { hasText: "AAPL" })).not.toBeVisible();
    await expect(page.locator("td", { hasText: "MEME" })).toBeVisible();
    // Clear filter
    await page.getByPlaceholder("Filter by ticker…").fill("");
    await expect(page.locator("td", { hasText: "AAPL" }).first()).toBeVisible();
  });
});
