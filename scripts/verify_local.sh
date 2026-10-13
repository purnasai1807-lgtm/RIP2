#!/usr/bin/env bash
set -euo pipefail

# Run from the project root after installing requirements.txt.
python -m compileall -q app migrations tests
python -m pytest -q

if command -v docker >/dev/null 2>&1; then
  docker compose config --quiet
  docker compose -f docker-compose.local.yml config --quiet
else
  echo "SKIP: Docker is not installed; Compose validation was not run." >&2
fi

echo "Local verification commands completed. PostgreSQL concurrency, SMTP, restore, and load tests still require staging."
