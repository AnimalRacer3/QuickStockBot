/**
 * Section 17 — Full pipeline E2E test.
 *
 * Covers (per delta requirements):
 *   1. Connect with connection password
 *   2. Live log feed — real-time events visible in browser
 *   3. Scanner pass with an unknown-float row (MEME)
 *   4. Front-side momentum entry on tradable top-N leader (AAPL)
 *   5. Trail-off exit scaling out across candles
 *   6. Daily-limit halt firing
 *   7. Trade in history with full status timeline (partial_exit + exited)
 *   8. Calendar day populating with correct color (+green) and amount
 *   9. Settings change taking effect on the bot
 */

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
  await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15_000 });
}

test.describe("Pipeline — full bot → relay → dashboard flow", () => {
  test("connect with password and receive live log feed", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    const logRegion = page.getByRole("log");
    await expect(logRegion).toBeVisible();
    // The mock relay sends "scanner idle" after subscribe_logs and also via web_auth pipeline
    await expect(page.getByText(/scanner idle/i)).toBeVisible({ timeout: 8000 });
  });

  test("scanner pass surfaces unknown-float ticker and tradable leader", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    // The pipeline logs fired after auth include the scanner pass message
    await expect(page.getByText(/scanner pass complete/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/unknown float/i)).toBeVisible({ timeout: 5000 });

    // Active tickers page must show AAPL (tradable leader) and MEME (unknown-float badge)
    await page.getByRole("link", { name: "Active Tickers" }).click();
    await page.waitForURL("**/tickers", { timeout: 5000 });
    await expect(page.getByText("AAPL")).toBeVisible({ timeout: 8000 });
    await expect(page.getByTestId("unknown-float-badge")).toBeVisible();
  });

  test("front-side momentum entry log appears after scanner pass", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    // Mock relay fires ENTRY log ~700 ms after auth_ok
    await expect(page.getByText(/ENTRY AAPL/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/front-side momentum/i)).toBeVisible();
  });

  test("trail-off exit: multiple PARTIAL EXIT log lines then full EXIT", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    // Two partial exits at candle boundaries, then a final exit
    const logRegion = page.getByRole("log");
    await expect(logRegion.getByText(/PARTIAL EXIT AAPL/i).first()).toBeVisible({ timeout: 10_000 });
    await expect(logRegion.getByText(/PARTIAL EXIT AAPL/i).nth(1)).toBeVisible({ timeout: 5000 });
    await expect(logRegion.getByText(/EXIT AAPL.*bullishness ended/i)).toBeVisible({ timeout: 5000 });
  });

  test("daily-limit halt fires and appears in live log", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    await expect(page.getByText(/HALT.*daily profit target/i)).toBeVisible({ timeout: 12_000 });
    await expect(page.getByText(/no new entries/i)).toBeVisible();
  });

  test("trade history — trail-off trade has full status timeline", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    await page.getByRole("link", { name: "Trade History" }).click();
    await page.waitForURL("**/history", { timeout: 5000 });
    await expect(page.getByText("AAPL")).toBeVisible({ timeout: 8000 });

    // trade-003 has net_pl = 75.00; click that row to open the detail view
    const trailRow = page.locator("tr").filter({ hasText: "75.00" }).first();
    await expect(trailRow).toBeVisible({ timeout: 5000 });
    await trailRow.click();

    // Status History section must show the lifecycle
    await expect(page.getByText("Status History")).toBeVisible({ timeout: 5000 });
    // Two partial exits
    await expect(page.getByText("partial_exit").first()).toBeVisible();
    await expect(page.getByText("partial_exit").nth(1)).toBeVisible();
    // Final full exit
    await expect(page.getByText("exited")).toBeVisible();
    // Fill prices for each step
    await expect(page.getByText("15.60", { exact: false })).toBeVisible();
    await expect(page.getByText("16.00", { exact: false })).toBeVisible();
    await expect(page.getByText("16.50", { exact: false })).toBeVisible();
  });

  test("calendar — March 2024 day-5 is green with correct profit amount", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    await page.getByRole("link", { name: "Calendar" }).click();
    await page.waitForURL("**/calendar", { timeout: 5000 });
    await expect(page.getByLabel("Previous month")).toBeVisible({ timeout: 8000 });

    // Navigate back to March 2024
    for (let i = 0; i < 30; i++) {
      if (await page.locator("text=March 2024").isVisible()) break;
      await page.getByLabel("Previous month").click();
    }
    await expect(page.locator("text=March 2024")).toBeVisible({ timeout: 5000 });

    // March 5 ($120 profit from trade-001+trade-003) should render as green
    const profitDay = page.getByTestId("calendar-day-2024-03-05");
    await expect(profitDay).toBeVisible();
    await expect(profitDay).toHaveAttribute("data-color", "green");

    // P/L chip: fmtDay(120) → "+120"
    const plChip = page.getByTestId("calendar-pl-2024-03-05");
    await expect(plChip).toBeVisible();
    await expect(plChip).toHaveText("+120");

    // Click to open the day detail and verify trades are listed
    await profitDay.click();
    await expect(page.getByText("2024-03-05")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("AAPL")).toBeVisible();
  });

  test("settings change — switch exit_mode to trail_off and save", async ({ page }) => {
    await connect(page);
    await waitForConnected(page);

    await page.getByRole("link", { name: "Settings" }).click();
    await page.waitForURL("**/settings", { timeout: 5000 });
    await expect(page.getByText("Exit Mode")).toBeVisible({ timeout: 10_000 });

    await page.locator("label", { hasText: "Trail Off" }).click();
    await expect(page.getByText("Trail Off Trigger (%)")).toBeVisible();

    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByText("Settings saved.")).toBeVisible({ timeout: 5000 });
  });
});
