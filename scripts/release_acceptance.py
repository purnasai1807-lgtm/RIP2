"""Report release-gate readiness without claiming external checks ran.

This script performs only checks that are safe to run locally. External gates
are marked BLOCKED until an operator supplies real staging services and evidence.
It never prints secret values or sends network traffic.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks: list[tuple[str, str, str]] = []

    required_paths = [
        "app/__init__.py", "app/routes.py", "app/engine.py", "app/evidence.py",
        "app/integrations/college_source.py", "app/integrations/sync.py",
        "migrations/versions", "tests/test_app.py", "tests/test_college_source.py",
        "tests/test_evidence.py", "tests/browser/authenticated_smoke.py",
        "tests/load/locustfile.py", "scripts/verify_smtp.py",
        "scripts/verify_postgres_concurrency.py", "scripts/verify_backup_restore.sh",
        "scripts/run_load_matrix.sh", "scripts/evaluate_impact_cases.py",
    ]
    missing = [item for item in required_paths if not (ROOT / item).exists()]
    checks.append(("Repository module inventory", "PASS" if not missing else "FAIL",
                   "All expected module paths exist." if not missing else "Missing: " + ", ".join(missing)))

    required_env = ["DATABASE_URL", "MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME",
                    "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER", "COLLEGE_DATA_API_URL",
                    "COLLEGE_DATA_API_TOKEN", "PUBLIC_BASE_URL", "SECRET_KEY"]
    absent = [key for key in required_env if not os.environ.get(key, "").strip()]
    checks.append(("External service configuration", "BLOCKED" if absent else "CONFIGURED",
                   ("Not configured: " + ", ".join(absent) + ". Values are intentionally not displayed.")
                   if absent else "Required environment variables are present; connectivity is not proven."))

    checks.append(("Full Flask test suite", "BLOCKED" if importlib.util.find_spec("flask") is None else "READY",
                   "Flask dependency is unavailable in this environment; install requirements.txt to run it."
                   if importlib.util.find_spec("flask") is None else "Dependencies may be present; run pytest to establish results."))
    checks.append(("PostgreSQL migration/concurrency/restore", "BLOCKED",
                   "Requires a disposable PostgreSQL instance and recorded successful execution of migration, concurrency, backup and restore scripts."))
    checks.append(("SMTP verification and reset delivery", "BLOCKED",
                   "Requires real SMTP settings and confirmation that verification and reset messages reach the test inbox."))
    checks.append(("Official ACEEC ERP/SIS reconciliation", "BLOCKED",
                   "Requires written authorization, provider contract/credentials, and owner-reviewed reconciliation results."))
    checks.append(("Browser role acceptance", "BLOCKED",
                   "Requires a deployed staging URL and test accounts for student, faculty, and administrator roles."))
    checks.append(("50/100/250/500-user performance", "BLOCKED",
                   "Requires controlled HTTPS staging; run scripts/run_load_matrix.sh and review generated metrics."))
    checks.append(("Stakeholder impact-model validation", "BLOCKED",
                   "Requires a non-empty, approved reviewer-labeled dataset; no ground truth is fabricated by this script."))
    checks.append(("Production security/release approval", "BLOCKED",
                   "Requires secret-manager/HTTPS review, restore drill, security review, and signed staging acceptance."))

    for name, status, detail in checks:
        print(f"[{status}] {name}: {detail}")
    blocked = sum(status == "BLOCKED" for _, status, _ in checks)
    failed = sum(status == "FAIL" for _, status, _ in checks)
    print(f"\nSummary: {len(checks)} gates; {blocked} externally blocked; {failed} repository failures.")
    print("This is a readiness report, not proof of production acceptance.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
