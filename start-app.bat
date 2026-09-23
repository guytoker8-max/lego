@echo off
rem Open the Kitsnap phone app in Expo Go. Needs Node.js 22 (nodejs.org) and
rem the Expo Go app on your phone. Scan the QR code with your phone when it
rem appears. Not on the same Wi-Fi? Run: start-app.bat --tunnel
cd /d "%~dp0app"
echo Installing the app (first run takes a few minutes)...
call npm install --no-audit --no-fund
echo.
echo Starting Kitsnap. Scan the QR code below with your phone.
call npx expo start %*
