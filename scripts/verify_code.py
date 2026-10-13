#!/usr/bin/env python3
"""Run checks that can execute without the Flask app dependencies or external services.

This deliberately does not label a project production-ready. It runs Python compilation,
the migration graph validator, the dependency-light unit tests, and the impact demo.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ("Python syntax compilation", [sys.executable, "-m", "compileall", "-q", "app", "migrations", "tests", "scripts"]),
    ("Migration graph", [sys.executable, "scripts/validate_migration_graph.py"]),
    ("Dependency-light tests", [sys.executable, "-m", "pytest", "-q", "tests/test_evidence.py", "tests/test_college_source.py", "tests/test_preflight.py", "tests/test_impact_evaluation.py", "tests/test_smtp_probe.py", "tests/test_backup_restore_guard.py", "tests/test_route_authorization_static.py"]),
]

def main() -> int:
    failures = []
    for label, command in CHECKS:
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        print(f"[{ 'PASS' if result.returncode == 0 else 'FAIL' }] {label} (exit {result.returncode})", flush=True)
        if result.returncode:
            failures.append(label)
    print("\n=== Result ===")
    if failures:
        print("Checks failed: " + ", ".join(failures))
        print("This report covers only the checks listed above; run the full suite and external acceptance gates separately.")
        return 1
    print("All local dependency-light checks passed.")
    print("NOT VERIFIED: full Flask route suite, PostgreSQL integration, SMTP delivery, official ACEEC ERP/SIS reconciliation, browser acceptance, production deployment, backup restore, and load capacity.")
    print("The demo CLI intentionally requires an operator-supplied, authorized real-data JSON file; this verifier will not fabricate one.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
