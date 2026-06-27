# PyInstaller spec — produces a single-file QuickStockBot installer executable.
#
# Build order matters — build the bot first, then the installer:
#   Linux/macOS:  bash ../scripts/build_dist.sh
#   Windows:      ..\scripts\build_dist.bat
#
# Or manually:
#   cd ../bot  && pyinstaller build.spec
#   cd ../installer && pyinstaller build.spec
#
# Output: installer/dist/quickstockbot-installer[.exe]
#
# The bot exe produced by bot/build.spec is bundled inside this installer
# so the user only needs to distribute a single file.

import sys
from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

block_cipher = None

_bot_exe_name = "quickstockbot.exe" if sys.platform == "win32" else "quickstockbot"
_bot_exe_src = f"../bot/dist/{_bot_exe_name}"

a = Analysis(
    ["wizard/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[(_bot_exe_src, ".")],
    hiddenimports=[
        "wizard",
        "wizard.server",
        "wizard.config_writer",
        "wizard.validator",
        "wizard.reachability",
        "wizard.html_wizard",
        "flask",
        "flask.templating",
        "jinja2",
        "websockets",
        "websockets.asyncio",
        "httpx",
        "anyio",
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
    name="quickstockbot-installer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Windows: set console=False for a silent background process;
    # keep True during development for visible error output.
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
