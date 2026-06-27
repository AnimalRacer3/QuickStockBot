# PyInstaller spec — produces a single-file QuickStockBot bot executable.
#
# Build with:
#   cd bot && pyinstaller build.spec
#
# Output: bot/dist/quickstockbot[.exe]
#
# NOTE: Run this BEFORE building the installer so the installer can bundle
# the resulting exe. See scripts/build_dist.sh (Linux/macOS) or
# scripts/build_dist.bat (Windows).

import sys
from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

block_cipher = None

a = Analysis(
    ["run.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "bot",
        "bot.alpaca",
        "bot.alpaca.client",
        "bot.alpaca.config",
        "bot.alpaca.fake_client",
        "bot.control",
        "bot.control.db",
        "bot.control.handlers",
        "bot.control.local_api",
        "bot.control.relay_client",
        "bot.engine",
        "bot.engine.circuit_breaker",
        "bot.engine.config",
        "bot.engine.exits",
        "bot.engine.gate",
        "bot.engine.session",
        "bot.engine.sizing",
        "bot.learning",
        "bot.learning.config",
        "bot.learning.efficiency",
        "bot.learning.features",
        "bot.learning.labeling",
        "bot.learning.model",
        "bot.learning.prior_profit",
        "bot.license",
        "bot.license.validator",
        "bot.models",
        "bot.news",
        "bot.news.aggregator",
        "bot.news.config",
        "bot.news.models",
        "bot.news.providers.alpaca",
        "bot.news.providers.base",
        "bot.news.providers.benzinga",
        "bot.news.providers.finnhub",
        "bot.news.providers.newsapi",
        "bot.news.sentiment",
        "bot.news.service",
        "bot.scanner",
        "bot.ta",
        "dotenv",
        "fastapi",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.off",
        "websockets",
        "websockets.asyncio",
        "httpx",
        "anyio",
        "pydantic",
        "sklearn",
        "sklearn.linear_model",
        "sklearn.ensemble",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="quickstockbot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
