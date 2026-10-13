@echo off
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Virtual environment not found. Run scripts\setup_windows.cmd first.
  exit /b 1
)
set "PY=.venv\Scripts\python.exe"
echo === Phase 1: Python syntax ===
%PY% -m compileall -q app migrations tests scripts
if errorlevel 1 exit /b 1
echo PASS: Python syntax

echo === Phase 1: migration graph ===
%PY% scripts\validate_migration_graph.py
if errorlevel 1 exit /b 1
echo === Phase 1: full pytest suite ===
%PY% -m pytest -q
if errorlevel 1 (
  echo FAIL: Full pytest suite. Review the traceback above and fix before marking Phase 1 complete.
  exit /b 1
)
echo === Phase 1: dependency-light verifier ===
%PY% scripts\verify_code.py
if errorlevel 1 exit /b 1
echo PASS: Phase 1 automated checks. Manually verify local startup and core workflows before closing Phase 1.
exit /b 0
