"""Run a local, non-destructive preflight before a hackathon demo/submission."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "app/__init__.py", "app/routes.py", "app/engine.py", "app/evidence.py",
    "app/integrations/college_source.py", "app/integrations/sync.py",
    "app/templates/landing.html", "app/templates/dashboard.html",
    "app/templates/scenario_detail.html", "app/templates/scenario_compare.html",
    "docs/hackathon/JUDGE_DEMO_RUNBOOK.md", "docs/hackathon/PROJECT_PITCH.md",
    "docs/hackathon/ARCHITECTURE.md", "docs/hackathon/SUBMISSION_CHECKLIST.md",
]

def main() -> int:
    failures = 0
    for relative in REQUIRED:
        ok = (ROOT / relative).is_file()
        print(f"[{'PASS' if ok else 'FAIL'}] Required artifact: {relative}")
        failures += not ok
    for module in ("flask", "flask_sqlalchemy", "flask_login", "flask_migrate", "psycopg"):
        ok = importlib.util.find_spec(module) is not None
        print(f"[{'PASS' if ok else 'BLOCKED'}] Python dependency available: {module}")
    secret = os.getenv("SECRET_KEY", "")
    if secret and len(secret) >= 32 and secret not in {"change-me", "dev-secret", "replace-me"}:
        print("[PASS] SECRET_KEY appears configured (value not printed)")
    else:
        print("[INFO] SECRET_KEY not configured for this shell; set a unique value before running the app")
    print("\nThis preflight checks repository/dependency readiness only; it does not prove staging, email, ERP/SIS, or production acceptance.")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
