@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Virtual environment is missing. Run scripts\setup_windows.cmd first.
  exit /b 1
)

rem Disposable local-only secret. Use a managed, unique secret for any shared deployment.
if not defined SECRET_KEY set "SECRET_KEY=local-only-ripple-development-secret-change-before-sharing"
if not defined APP_ENV set "APP_ENV=development"
if not defined COOKIE_SECURE set "COOKIE_SECURE=false"

.venv\Scripts\python.exe -m compileall -q app migrations
if errorlevel 1 exit /b 1

echo Starting THE RIPPLE at http://127.0.0.1:5000
.venv\Scripts\python.exe -m flask --app wsgi:app run --host 127.0.0.1 --port 5000
