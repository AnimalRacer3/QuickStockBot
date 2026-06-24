# QuickStockBot Installer

One-click setup for end users. Downloads the bot and relay binaries, writes config, and registers them as system services.

## Status

Placeholder — implementation coming in a future section.

## Planned Features

- Interactive setup wizard (license key, broker credentials, watchlist)
- Downloads and verifies signed bot + relay binaries
- Writes `.env` files for both `bot/` and `relay/`
- Registers as systemd service (Linux) or launchd plist (macOS)
- Provides `quickstockbot start / stop / update` CLI commands
