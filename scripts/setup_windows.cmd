@echo off
setlocal
cd /d "%~dp0\.."

echo === THE RIPPLE: Windows setup ===
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python Launcher 'py' was not found.
  echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
  echo Enable the Python Launcher during installation, then reopen this terminal.
  exit /b 1
)

py -3 --version
if errorlevel 1 (
  echo ERROR: Python 3 could not be launched. Install Python 3.11 or newer.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)

.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed. Check your internet connection and pip output.
  exit /b 1
)

if not exist ".env" (
  copy /Y .env.local.example .env >nul
  if errorlevel 1 echo WARNING: Could not copy .env.local.example. The local app can still use SQLite defaults.
)

echo.
echo Setup completed. Next run scripts\run_windows.cmd
exit /b 0
