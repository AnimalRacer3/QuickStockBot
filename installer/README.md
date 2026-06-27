# QuickStockBot Installer

One-click setup wizard for end users. Packages everything into a single
executable, opens a local web wizard in the user's browser, validates all
inputs, confirms relay reachability, writes config to disk, and installs
autostart.

## Structure

```
installer/
├── wizard/
│   ├── __main__.py      # Entry point — starts Flask server, opens browser
│   ├── server.py        # Flask wizard server (API routes)
│   ├── config_writer.py # Writes .env + config.json, sets up autostart
│   ├── validator.py     # Input validation (Alpaca keys, URLs, risk params)
│   ├── reachability.py  # Relay round-trip reachability check
│   └── html_wizard.py   # Embedded single-page wizard HTML/JS
├── tests/
│   ├── test_config_writer.py
│   ├── test_validator.py
│   ├── test_reachability.py
│   └── test_smoke.py    # Flask app + packaging smoke tests
├── pyproject.toml
└── build.spec           # PyInstaller spec
```

## Development

```bash
cd installer
uv sync --group dev
uv run pytest -v
```

## Building the executable

```bash
cd bot
uv run pyinstaller build.spec
cd ../installer
uv run pyinstaller build.spec
```

## Wizard flow

1. **Connection** — Relay URL + license key
2. **Security** — Connection password (≥ 8 chars, confirmed)
3. **Alpaca Paper Keys** — API key + secret, with live test button
4. **Alpaca Live Keys** — Optional, for real-money trading
5. **News APIs** — Finnhub / NewsAPI / Benzinga (all optional; Alpaca news is default)
6. **Scanner** — Pre-open lead hours, scan duration, RVOL min, gap-up %, float cap,
   include-unknown-float, active tickers N
7. **Patterns & MACD** — Enabled patterns, candle lookback, MACD periods,
   enforce-above-zero
8. **Risk & Exits** — Daily max-loss %, profit target %, risk override, exit mode,
   trail-off options
9. **Connect & Install** — Relay reachability check → shows stable bot URL →
   writes config → sets up autostart

## Config output

Secrets are written to `~/.quickstockbot/.env` (mode 0600 on POSIX) and never
appear in logs. Non-secret tunables go to `~/.quickstockbot/config.json`.

## Autostart

| OS      | Method                                       |
| ------- | -------------------------------------------- |
| Windows | Windows Task Scheduler (`ONLOGON`, elevated) |
| Linux   | systemd user service (`~/.config/systemd`)   |
| macOS   | launchd plist (`~/Library/LaunchAgents`)     |

## Uninstall

The wizard's install API (`POST /api/uninstall`) removes the config directory
and all autostart entries. On Windows, run the exe and use the uninstall
option; on Linux/macOS, `quickstockbot-installer --uninstall`.
