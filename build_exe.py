#!/usr/bin/env python3
"""Build dist/trader.exe with PyInstaller (one-file).

Run from the repo root:
    python build_exe.py

config.yaml and .env are NOT bundled -- they're read from the directory
containing the exe at runtime (see trader/config.py: app_dir()).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", "trader",
        "--onefile",
        "--console",
        "--clean",
        "--paths", str(ROOT),
        # These are imported lazily inside function bodies (mcp_robinhood.py,
        # alpaca_data.py), so PyInstaller's static import scanner misses them.
        "--hidden-import", "mcp",
        "--hidden-import", "mcp.client.stdio",
        "--hidden-import", "mcp.client.sse",
        "--hidden-import", "mcp.types",
        "--collect-submodules", "anthropic",
        "--hidden-import", "alpaca.data.live.stock",
        "--hidden-import", "alpaca.data.historical.stock",
        "--hidden-import", "alpaca.data.historical.screener",
        "--hidden-import", "alpaca.trading.client",
        str(ROOT / "trader" / "main.py"),
    ]
    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    print()
    print("Build complete: dist/trader.exe (or dist/trader on non-Windows).")
    print("Copy config.yaml and .env next to the exe before running it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
