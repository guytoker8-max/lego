@echo off
rem Open the Kitsnap phone app in Expo Go.
rem Double-click this file. Needs Node.js 22 (nodejs.org) on this computer and
rem the Expo Go app on your phone. Scan the QR code with your phone when it
rem appears. Phone on a different Wi-Fi? Run: start-app.bat --tunnel
title Kitsnap
cd /d "%~dp0app"

where node >/dev/null 2>nul
if errorlevel 1 (
  echo.
  echo Node.js is not installed, or this window was opened before it was.
  echo Install the LTS version from https://nodejs.org, restart the computer,
  echo then double-click start-app.bat again.
  echo.
  pause
  exit /b 1
)

for /f "tokens=1 delims=v." %%v in ('node -v') do set NODE_MAJOR=%%v
if %NODE_MAJOR% LSS 22 (
  echo.
  echo This computer has an old Node.js. Kitsnap needs version 22 or newer.
  echo Install the LTS version from https://nodejs.org, then try again.
  echo.
  pause
  exit /b 1
)

echo Installing the app. The first run takes a few minutes...
call npm install --no-audit --no-fund
if errorlevel 1 (
  echo.
  echo The install failed. Check the internet connection and try again.
  echo If it keeps failing, send a photo of this window.
  echo.
  pause
  exit /b 1
)

echo.
echo Starting Kitsnap. Scan the QR code below with your phone.
echo Keep this window open while you use the app. Close it to stop.
echo.
call npx expo start %*
echo.
pause
