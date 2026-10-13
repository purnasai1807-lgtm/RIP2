#!/usr/bin/env bash
# One-shot acceptance gate. External tests are opt-in and require dedicated test systems.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m compileall -q app migrations tests scripts
python scripts/validate_migration_graph.py
python -m pytest -q
if [[ "${RUN_POSTGRES_ACCEPTANCE:-false}" == "true" ]]; then
  python scripts/verify_postgres_guards.py
  python scripts/verify_postgres_concurrency.py
fi
if [[ "${RUN_SMTP_ACCEPTANCE:-false}" == "true" ]]; then
  python scripts/verify_smtp.py
fi
if [[ "${RUN_BROWSER_ACCEPTANCE:-false}" == "true" ]]; then
  python tests/browser/authenticated_smoke.py
fi
if [[ "${RUN_OFFICIAL_INTEGRATION_PREVIEW:-false}" == "true" ]]; then
  python scripts/verify_official_integration.py
fi
if [[ "${RUN_DEPLOYMENT_SMOKE:-false}" == "true" ]]; then
  python scripts/smoke_test_deployment.py
fi
if [[ "${RUN_LOAD_TEST:-false}" == "true" ]]; then
  : "${LOAD_TEST_HOST:?Set LOAD_TEST_HOST to the staging URL}"
  : "${LOAD_TEST_EMAIL:?Set LOAD_TEST_EMAIL to a dedicated synthetic account}"
  : "${LOAD_TEST_PASSWORD:?Set LOAD_TEST_PASSWORD to its password}"
  locust -f tests/load/locustfile.py --headless -H "$LOAD_TEST_HOST" --users "${LOAD_USERS:-50}" --spawn-rate "${LOAD_SPAWN_RATE:-5}" --run-time "${LOAD_DURATION:-5m}" --csv "${LOAD_RESULTS_PREFIX:-load-results}"
fi
printf '\nRelease acceptance checks completed for enabled gates only. Review the output and retain logs.\n'
