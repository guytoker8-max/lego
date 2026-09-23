@echo off
rem Start the BrickSnap website on this computer: http://localhost:8000
rem Needs Python 3.10+ and Node.js 18+. Payments run in test mode.
cd /d "%~dp0"
echo Installing the website (first run takes a few minutes)...
cd web
call npm install --no-audit --no-fund || goto :fail
call npx vite build || goto :fail
cd ..\server
python -m venv .venv || goto :fail
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt || goto :fail
if "%BRICKSNAP_ADMIN_TOKEN%"=="" set BRICKSNAP_ADMIN_TOKEN=admin
echo.
echo BrickSnap is running. Open http://localhost:8000  (orders screen: /ops, token: %BRICKSNAP_ADMIN_TOKEN%)
echo Close this window to stop.
start "" http://localhost:8000
uvicorn app.main:app --port 8000
goto :eof
:fail
echo Something went wrong above. Check that Python and Node.js are installed.
pause
