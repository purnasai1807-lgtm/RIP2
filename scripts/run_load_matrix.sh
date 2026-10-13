#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_HOST:?Set TARGET_HOST to the HTTPS staging URL}"
: "${LOAD_TEST_EMAIL:?Set LOAD_TEST_EMAIL to an approved synthetic @aceec.ac.in staging account}"
: "${LOAD_TEST_PASSWORD:?Set LOAD_TEST_PASSWORD to that synthetic account password}"
: "${LOAD_TEST_DURATION:=3m}"
: "${LOAD_TEST_SPAWN_RATE:=10}"
: "${LOAD_TEST_OUTPUT_DIR:=load-results}"

case "$TARGET_HOST" in
  https://*) ;;
  *) echo "Refusing non-HTTPS target. Use a staging HTTPS URL." >&2; exit 2 ;;
esac
if [[ "$TARGET_HOST" == *"localhost"* || "$TARGET_HOST" == *"127.0.0.1"* ]]; then
  echo "Refusing localhost: run this matrix against a controlled staging environment." >&2
  exit 2
fi
command -v locust >/dev/null || {
  echo "Locust missing. Install: pip install -r requirements-load-test.txt" >&2; exit 2;
}
mkdir -p "$LOAD_TEST_OUTPUT_DIR"
export LOAD_TEST_EMAIL LOAD_TEST_PASSWORD
for users in 50 100 250 500; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  prefix="${LOAD_TEST_OUTPUT_DIR}/${stamp}-${users}-users"
  echo "Running ${users} users against ${TARGET_HOST}; results prefix: ${prefix}"
  locust -f tests/load/locustfile.py --headless --host "$TARGET_HOST" \
    --users "$users" --spawn-rate "$LOAD_TEST_SPAWN_RATE" --run-time "$LOAD_TEST_DURATION" \
    --csv "$prefix" --csv-full-history --html "${prefix}.html"
done
echo "Load matrix completed. Review HTML/CSV for p95/p99 latency, failure rate, throughput and saturation."
echo "This script does not certify production readiness; review results against approved acceptance thresholds."
