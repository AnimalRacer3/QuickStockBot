# QuickStockBot -- standalone day-trading bot

A self-contained, rule-based day-trading bot for US equities. Plain Python
3.11+, packaged with PyInstaller into a single `trader.exe` for Windows 11.
Claude is used for exactly one thing per day: verifying news catalysts and
ranking the 9:15 AM watchlist. Everything else -- pattern detection, entries,
exits, risk management, position sizing -- is deterministic code.

## Architecture

```
trader/
  config.py           config.yaml + .env loading, validation
  logging_setup.py     daily rotating log, secret redaction
  lock.py              single-instance lock file
  models.py            shared dataclasses (Candle, Position, WatchlistEntry, ...)
  market_calendar.py   Alpaca calendar/clock; holiday & early-close handling
  alpaca_data.py       Alpaca data layer: screening, bars, RVOL, websocket/polling stream
  indicators.py        pure VWAP / MACD / RVOL / volume-confirmation functions
  patterns.py          candlestick pattern detectors (3-6 candle formations only)
  mcp_robinhood.py     Robinhood MCP client: discovery, role-mapping, order calls
  anthropic_select.py  the one daily Claude call (9:15 ticker selection)
  risk.py              position sizing, stop/target/trail-off, circuit breakers
  execution.py         live order placement + DRY_RUN / replay fill simulation
  journal.py           trade journal, skip log, runs.csv, performance_db.json
  reporting.py         end-of-day Markdown report
  engine.py            daily lifecycle orchestration (live)
  replay.py            --replay mode (same engine logic, recorded bars)
  selftest.py          --selftest connectivity checks
  main.py              CLI entrypoint
scripts/
  record_bars.py       records a day's Alpaca bars + watchlist for --replay
tests/                 pytest unit tests (patterns, risk, calendar)
config.yaml            default config (copy next to the exe)
.env.example           secret template (copy to .env next to the exe)
build_exe.py           PyInstaller one-file build script
```

### External services

- **Alpaca** (data layer, authoritative for analytics/candles): market
  calendar/clock, pre-market gapper screening, 1-minute candles (websocket
  preferred, polling fallback), RVOL, historical bars, MACD inputs.
  Keys: `ALPACA_KEY` / `ALPACA_SECRET` in `.env`.
- **Robinhood MCP** (brokerage layer, authoritative for account state and
  execution): account equity/buying power, positions, a fresh quote
  sanity-check immediately before every order, and all order placement. The
  bot connects as a plain MCP client to whatever Robinhood MCP server is
  already configured for Claude Code on the machine (read from `.mcp.json`
  or `~/.claude.json`, falling back to `claude mcp list`) and reuses its
  stored auth. Tool names are **never hardcoded** -- at startup the bot lists
  the server's tools and fuzzy-maps them to the roles it needs
  (`get_account`, `get_positions`, `get_quote`, `place_order`,
  `cancel_order`, `order_status`), failing loudly if a role can't be found
  or auth is rejected.
- **Anthropic API** (judgment layer, one call/day): `ANTHROPIC_API_KEY` in
  `.env`. Used only for the 9:15 catalyst-verification/ranking call, with
  the server-side web-search tool enabled. The model is a config option
  (`anthropic.model` in `config.yaml`).

**Priority rule:** if the Alpaca feed fails mid-session, the bot manages
*existing* positions off Robinhood quotes (stops/targets only) and takes no
new entries. If the Robinhood MCP connection fails, the bot halts all
trading immediately.

## config.yaml

Lives next to `trader.exe`, hand-edited, never committed with secrets.
`mode: DRY_RUN` (default) simulates fills; switch to `LIVE` only by manually
editing the file. On `LIVE`, the bot prints a 10-second warning banner (with
the computed kill-switch dollar amount) before the trading loop starts. See
the shipped `config.yaml` for every tunable (kill-switch %, position sizing,
stop/target/trail-off %, screening thresholds, pattern toggles, Anthropic
model choice, file paths).

## .env

Copy `.env.example` to `.env` next to the exe and fill in:

```
ALPACA_KEY=...
ALPACA_SECRET=...
ANTHROPIC_API_KEY=...
```

Never commit this file. Secrets are never logged (see
`trader/logging_setup.py`'s redaction filter).

## Daily lifecycle

1. **Startup** (scheduler launches ~9:15 ET): load config/secrets, acquire
   a lock file, connect Alpaca + Robinhood MCP, snapshot starting equity.
2. **Market calendar check**: holiday/weekend -> log + zero-trade report +
   exit 0. Early close -> all close-relative times (force-close, z-hour
   cutoff) are computed from the actual close, never hardcoded 16:00.
3. **9:15 ticker selection**: a mechanical Alpaca screen (price range, RVOL,
   float, MACD) produces up to 15 candidates, then **one** Anthropic call
   (with web search) verifies catalysts and returns a ranked, strict-JSON
   watchlist. Malformed JSON is retried once; two failures (or an empty /
   no-trade-day result) -> zero-trade report + exit 0. The exact
   request/response and cost are logged to `trading/logs/`.
4. **9:30 re-validation**: each watchlist ticker is re-checked against live
   criteria; survivors are frozen for the day (no new symbols added).
5. **Monitoring loop**: pure rules, evaluated on every completed 1-minute
   candle -- pattern completion, VWAP/overextension, MACD, volume
   confirmation, free position slot, before the z-hour cutoff.
6. **Exits** (priority order): take-profit -> stop-loss -> trail-off
   scale-out -> VWAP-loss-with-volume -> force-close at close minus the
   configured offset.
7. **Shutdown triggers**: kill-switch (-10% of starting equity), profit
   giveback (25% off the day's green peak -- blocks new entries only),
   no-trade cutoff (zero entries by open + 2h), or normal end-of-day.

Exit codes: `0` clean day / closed market, `2` kill-switch, `3` config/auth
error, `4` data-feed failure.

## Candlestick patterns (3-6 candles only, each independently toggleable)

- **Morning Star** (3): red -> small indecision candle holding the low ->
  green closing above the first candle's midpoint, on rising volume.
- **Three White Soldiers** (3): three green candles, each opening within
  the prior body, closing near its high, steady volume.
- **Rising Three Methods** (5): strong green -> 3 small pullback candles
  holding the first candle's low -> green closing above the first candle's
  high.
- **Pullback / bull flag** (4-6): a 1-2 candle surge on heavy volume -> 2-4
  orderly pullback candles with declining volume, holding VWAP and above a
  50% retrace -> entry the instant price breaks the prior candle's high.
- **Breakout base** (3-6): a tight (<~2%) consolidation on declining volume,
  broken by a candle clearing the base high on >=2x base volume.

Every entry is tagged in the journal with its pattern name and the exact
candle timestamps that formed it.

## Logging & reporting

- `trading/journal/<date>-trades.json` -- per-trade records (fill, pattern +
  candle timestamps, stop, target, exit, P&L $/%, exit reason).
- `trading/journal/<date>-skips.json` -- every skipped signal with a reason.
- `trading/logs/<date>.log` -- daily rotating text log (secrets redacted).
- `trading/logs/<date>-claude.log` -- the day's Claude request/response/cost.
- `trading/runs.csv` -- one row per day (date, mode, result, Claude cost, P&L).
- `trading/performance_db.json` -- rolling per-ticker and per-pattern stats.
- `trading/<date>-report.md` -- end-of-day report (headline P&L, trade
  table, skip-reason counts, watchlist vs. outcome, proven performers, or
  the zero-trade variant).

## Building `trader.exe`

On Windows 11, with Python 3.11+ installed:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python build_exe.py
```

This produces `dist\trader.exe`. Copy `config.yaml` and your `.env` into
`dist\` next to it -- both are read from the exe's own directory at
runtime, never bundled into the binary.

## First run

1. **Unit tests** (from the repo, not the exe):
   ```
   pip install -r requirements-dev.txt
   pytest
   ```
2. **`--selftest`** -- checks `.env` keys, Alpaca connectivity, Robinhood
   MCP connection + role mapping, and Anthropic API reachability. Run this
   after every fresh install and whenever credentials change:
   ```
   trader.exe --selftest
   ```
   It prints a PASS/FAIL table and exits non-zero on any FAIL. The
   Robinhood MCP check requires the same machine's Claude Code to already
   have a Robinhood MCP server configured (`.mcp.json` / `~/.claude.json`
   / `claude mcp list`) -- if it isn't, that row fails until it's set up.
3. **`--replay <date>`** -- validate pattern/risk behavior against a
   recorded day without waiting for market hours:
   ```
   python scripts\record_bars.py --date 2026-06-14 --tickers AAPL,TSLA
   trader.exe --replay 2026-06-14
   ```
   Replay skips the Claude call entirely (it reuses the saved watchlist),
   and skips the Robinhood MCP connection (fills are simulated against the
   recorded candle closes with a small synthetic spread) -- it only
   exercises the Alpaca-data-driven pattern/risk/journal/report path.
4. **First `DRY_RUN` launch** -- with `config.yaml`'s `mode: DRY_RUN` (the
   shipped default) and a real `.env`, just run `trader.exe` around 9:15 ET
   on a trading day (or via your Windows Task Scheduler). It will do the
   full lifecycle -- screen, one Claude call, 9:30 re-validation, the
   monitoring loop -- but every fill is simulated pessimistically (enter at
   ask, exit at bid, spread logged as slippage) and no live orders are
   ever placed. Check `trading\<date>-report.md` afterward.
5. Only after a clean `--selftest` and a DRY_RUN day (or several) you're
   comfortable with, switch `mode: LIVE` in `config.yaml` by hand. The bot
   will print a 10-second warning banner with the computed kill-switch
   dollar amount before the loop starts on the first LIVE day.

## Notes on the mechanical screen

Alpaca doesn't expose a dedicated "pre-market gappers" endpoint; the screen
uses Alpaca's market-movers (top gainers) endpoint as the candidate universe,
then filters by price range, RVOL (vs. trailing 20-day average volume), MACD
bullishness, and flags unknown floats rather than hard-excluding them (many
small caps don't have float data in Alpaca's asset metadata). Tune
`price_min`/`price_max`/`min_rvol`/`max_float_millions` in `config.yaml` as
you observe live behavior.
