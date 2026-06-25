# QuickStockBot — User Setup Guide

> **Disclaimer:** QuickStockBot is a software tool, not a financial adviser.
> Nothing in this software or documentation constitutes financial advice,
> investment advice, or a recommendation to buy or sell any security.
> Past performance does not guarantee future results. Trade at your own risk.
>
> **Margin & PDT (post-June 4 2026):** The SEC/FINRA $25,000 PDT minimum has
> been removed. A $2,000 margin minimum now applies. Intraday buying power is
> intraday-margin-based. Each broker is phasing this in on its own timeline;
> QuickStockBot defers to Alpaca's reported `buying_power` and
> `pattern_day_trader` flag. If your account is below $2,000 or your broker
> has not yet migrated, use paper-trading mode until confirmed.

---

## Requirements

- macOS, Linux, or Windows 10/11
- Alpaca brokerage account (paper or funded)
- QuickStockBot subscription (start a free trial at quickstockbot.com)
- Python 3.11 or the pre-built installer binary (no Python required)

---

## Step 1 — Create an account and subscribe

1. Go to **quickstockbot.com** and click **Sign up**.
2. Enter your email and a strong password (8+ characters).
3. Open the verification email and click the confirmation link.
4. On the billing page choose the **Monthly** plan and complete Stripe checkout.
5. Your license key is emailed to you and also visible in the dashboard under
   **Account → License**.

---

## Step 2 — Install the bot

### Option A — One-click installer (recommended)

1. Download `quickstockbot-installer` for your platform from the dashboard
   **Downloads** page.
2. Run the installer:
   ```
   # macOS / Linux
   chmod +x quickstockbot-installer && ./quickstockbot-installer
   
   # Windows
   quickstockbot-installer.exe
   ```
3. Your browser opens the setup wizard at `http://localhost:7374`.

### Option B — pip (advanced users)

```
pip install quickstockbot-bot
python -m bot
```

---

## Step 3 — Setup wizard

The wizard walks you through:

| Step | What happens |
|------|-------------|
| **Broker credentials** | Enter your Alpaca API key and secret. Paper or live mode toggle. |
| **License key** | Paste the `QSB-XXXX-XXXX-XXXX-XXXX` key from your email. |
| **Connection password** | A random secret is auto-generated. The wizard saves it to your bot's `.env` and sends it to the relay during registration via HMAC-SHA256 proof. |
| **Risk settings** | Daily loss limit (%), daily profit target (%), position size (% of buying power), exit mode (dump vs. trail-off). |
| **Scanner settings** | Pre-open lead time, scan window duration, RVOL threshold, gap-up filter, float cap, unknown-float inclusion, top-N active tickers. |
| **Validate & launch** | The wizard tests connectivity to the relay and Alpaca, then registers the bot as a system service. |

---

## Step 4 — Connect the web dashboard

1. Go to the dashboard and click **Connect** in the sidebar.
2. Enter the **Relay URL** (shown in the wizard summary, e.g.
   `wss://relay.quickstockbot.com`).
3. Enter the **Connection Password** (same one the wizard generated).
4. Click **Connect**. The status indicator turns green.
5. Navigate to **Live Actions** — you should see real-time log lines from the
   bot within seconds.

---

## Dashboard pages at a glance

| Page | What it shows |
|------|--------------|
| **Live Actions** | Real-time log stream: scanner passes, entry/exit decisions, daily halt events. |
| **Active Tickers** | Top-N candidates from the last scanner pass. Shows RVOL, gap %, float, MACD favorability, patterns, score. Unknown-float rows are tagged with a badge. |
| **Trade History** | All closed trades with P/L, type, status. Click a row for the full status timeline (pending → filled → partial_exit… → exited). |
| **Calendar** | Daily P/L calendar. Green = profit, Red = loss, Blue = ran but flat. Click a day to see that day's trades. |
| **Settings** | Adjust risk limits, exit mode, and scanner parameters. Changes take effect on the bot immediately via RPC. |
| **Ticker Manager** | Maintain a manual watchlist and blacklist. |

---

## Scanner window

The scanner runs in a configurable pre-open window and for a set duration after
market open:

- **Pre-open lead** (`pre_open_lead_hours`): how many hours before market open
  the scanner starts collecting candidates.
- **Scan duration** (`scan_duration_hours`): how long after market open the
  scanner continues refreshing the active set.
- **Refresh interval** (`scanner_refresh_seconds`): how often the scanner
  re-evaluates and re-ranks candidates within the window.

Tickers outside the scan window appear greyed in the active set but are still
tracked for exit management.

---

## Unknown-float column

The **Unknown Float** column (and badge on the tickers page) indicates that
Finnhub returned no float-share data for that ticker. By default, unknown-float
tickers are shown but marked as non-tradable. Toggle
`include_unknown_float` in Settings to let the bot trade them.

---

## Exit modes

| Mode | Behaviour |
|------|-----------|
| **Dump** | Sells the entire position in one market order when the take-profit or reversal trigger fires. |
| **Trail Off** | Scales out a configurable fraction of remaining shares each candle while bullish momentum holds. Dumps the remainder when MACD goes below zero or a bearish pattern appears. |

The **Trail Off Trigger %** setting controls when trail-off scaling begins
(as a percentage above the entry price).

---

## Daily limits and the goal-post

- **Daily max loss %**: the bot flattens all positions and halts new entries
  when cumulative P/L (realized + unrealized) hits this level.
- **Daily profit target %**: optionally halts or flattens when the daily target
  is reached.
- **Goal-post trade count**: derived from `daily_max_loss / risk_per_trade`;
  shown in the settings panel as a guide to how many losing trades the day's
  budget allows.

Risk-sizing fields are greyed out when `override_risk_per_trade` is disabled —
the bot uses `daily_max_loss_pct` as the effective per-trade risk.

---

## Margin and PDT (post-June 4 2026)

The traditional $25,000 PDT rule has been superseded:

- **$2,000 margin minimum** replaces the $25,000 threshold.
- Intraday buying power is **intraday-margin-based**, not equity-capped.
- Brokers are phasing in the new rules; QuickStockBot defers entirely to
  Alpaca's reported `buying_power` and `pattern_day_trader` flag.
- If Alpaca still reports `pattern_day_trader: true`, the bot will not enter
  new positions until the flag clears.
- Accounts below $2,000 should remain in paper-trading mode.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Dashboard shows "Disconnected" | Wrong relay URL or password | Re-enter credentials on the Connect page |
| Bot logs "PDT flag active" | Alpaca still shows old PDT restriction | Contact Alpaca support or wait for broker migration |
| "License invalid" on startup | Key expired or revoked | Contact support at quickstockbot.com |
| No tickers appearing | Outside scan window, or all filtered out | Check scanner settings; lower RVOL or gap thresholds |
| "daily max loss hit" in logs | Normal circuit breaker | Resumes tomorrow automatically |
