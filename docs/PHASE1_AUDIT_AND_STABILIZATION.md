# Phase 1 — Audit and Stabilization Report

**Scope:** inspect the existing THE RIPPLE application, establish a reproducible baseline, verify repository structure and migration metadata, document local startup, and address Windows Command Prompt startup friction.

## Repository inventory

- Backend: Flask application factory in `app/__init__.py`, route handlers in `app/routes.py`, ORM models in `app/models.py`.
- Analysis: rule-based impact engine in `app/engine.py`; dataset analysis code in `app/dataset_engine.py`.
- Persistence: SQLAlchemy; SQLite is the local fallback; PostgreSQL is supported for deployment.
- Schema changes: Alembic/Flask-Migrate migrations under `migrations/versions/`.
- UI: Jinja templates under `app/templates/`, CSS and JavaScript under `app/static/`.
- Automated checks: `tests/` plus verification scripts under `scripts/`.
- Supplied dataset integration assets: `data/ripple_dataset/` (CSV and JSON source files; validate contents in Phase 2 before operational use).

## Changes made for Phase 1

1. Added `scripts/setup_windows.cmd` to create a virtual environment, install `requirements.txt`, and create a local `.env` only if one does not already exist.
2. Added `scripts/run_windows.cmd` to run syntax compilation and launch Flask on `http://127.0.0.1:5000` using the virtual environment. It does not require PowerShell-specific commands.
3. Added this audit report with explicit verification boundaries and next actions.
4. Preserved existing architecture and data-authenticity policy; no fabricated institutional records or live integration credentials were added.

## Verification performed in the build environment

| Check | Result | Notes |
|---|---|---|
| Python syntax compilation | PASS | `python -m compileall -q app migrations tests scripts` |
| Migration graph | PASS | 9 migrations form one linear chain, ending at `20261012_09_impact_feedback` |
| Dependency-light verification | PASS | `scripts/verify_code.py` reported 49 passing dependency-light tests |
| Deployment configuration preflight | PASS with warning | No local `SECRET_KEY` was configured in the build shell; the preflight warned appropriately |
| Hackathon preflight | BLOCKED in build environment | Required application dependencies were not installed in the isolated build environment |
| Full pytest suite | BLOCKED in build environment | Collection failed because Flask was unavailable; dependency installation could not reach package index from this environment |
| PostgreSQL connectivity | NOT RUN | No disposable PostgreSQL/Neon credentials were supplied |
| SMTP, official college API, browser E2E, production deploy, backup restore, load test | NOT RUN | Require external services/credentials and a controlled test environment |

## Important limitation

Phase 1 is not a claim that the complete application has passed its full route test suite or is production-ready. The full pytest suite must be rerun in the user's environment after installing `requirements.txt`. A successful syntax check or dependency-light test is not equivalent to a successful full application test.

## Windows Command Prompt instructions

From the extracted repository root, run:

```cmd
scripts\setup_windows.cmd
scripts\run_windows.cmd
```

Open `http://127.0.0.1:5000`. Keep the terminal open while using the app. Press `Ctrl+C` to stop the development server. These scripts are for local development only, not public production hosting.

Run tests after setup:

```cmd
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_code.py
.venv\Scripts\python.exe scripts\preflight.py
```

## Phase 1 exit criteria

- [x] Existing architecture and startup entry point identified.
- [x] Python syntax compiles in the build environment.
- [x] Migration graph validates.
- [x] Dependency-light checks pass.
- [x] Windows CMD setup and run helpers added.
- [ ] Full Flask pytest suite passes in an environment with requirements installed.
- [ ] App startup and `/healthz` are verified locally by the user.
- [ ] PostgreSQL/Neon connectivity is verified in a controlled environment.

The final three items require execution in an environment with the required dependencies and/or user-owned credentials; they cannot honestly be marked complete from this build environment.
