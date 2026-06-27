@echo off
REM Build both the bot exe and the installer exe.
REM
REM Usage (from repo root):
REM   scripts\build_dist.bat
REM
REM Output:
REM   bot\dist\quickstockbot.exe           <- standalone bot executable
REM   installer\dist\quickstockbot-installer.exe  <- installer (bundles the bot exe)

setlocal enabledelayedexpansion

set REPO_ROOT=%~dp0..

echo =^> Building bot executable...
cd /d "%REPO_ROOT%\bot"
pyinstaller build.spec --noconfirm
if errorlevel 1 (
    echo ERROR: Bot build failed.
    exit /b 1
)

echo.
echo =^> Building installer executable (bundles bot)...
cd /d "%REPO_ROOT%\installer"
pyinstaller build.spec --noconfirm
if errorlevel 1 (
    echo ERROR: Installer build failed.
    exit /b 1
)

echo.
echo Done.
echo   Bot:       %REPO_ROOT%\bot\dist\quickstockbot.exe
echo   Installer: %REPO_ROOT%\installer\dist\quickstockbot-installer.exe
