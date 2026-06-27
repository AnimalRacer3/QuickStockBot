#!/usr/bin/env bash
# Build both the bot exe and the installer exe.
#
# Usage (from repo root):
#   bash scripts/build_dist.sh
#
# Output:
#   bot/dist/quickstockbot          ← standalone bot executable
#   installer/dist/quickstockbot-installer  ← installer (bundles the bot exe)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building bot executable..."
cd "$REPO_ROOT/bot"
pyinstaller build.spec --noconfirm

echo ""
echo "==> Building installer executable (bundles bot)..."
cd "$REPO_ROOT/installer"
pyinstaller build.spec --noconfirm

echo ""
echo "Done."
echo "  Bot:       $REPO_ROOT/bot/dist/quickstockbot"
echo "  Installer: $REPO_ROOT/installer/dist/quickstockbot-installer"
