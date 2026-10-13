@echo off
setlocal
cd /d "%~dp0"
echo ========================================================
echo              THE RIPPLE - ripple111
echo ========================================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 goto :fail
)
echo Installing or checking required Python packages...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :fail
if not defined SECRET_KEY set "SECRET_KEY=local-only-ripple111-development-secret-change-before-sharing"
if not defined APP_ENV set "APP_ENV=development"
if not defined COOKIE_SECURE set "COOKIE_SECURE=false"
.venv\Scripts\python.exe -m compileall -q app migrations
if errorlevel 1 goto :fail
echo.
echo Starting THE RIPPLE at http://127.0.0.1:5000
echo Use Ctrl+C to stop the server.
start "THE RIPPLE browser" http://127.0.0.1:5000
.venv\Scripts\python.exe -m flask --app wsgi:app run --host 127.0.0.1 --port 5000
exit /b %errorlevel%
:fail
echo.
echo Startup failed. Read the error above; package installation requires internet access.
pause
exit /b 1
