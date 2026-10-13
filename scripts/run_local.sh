#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for the one-command local PostgreSQL setup." >&2
  echo "Install Docker Desktop, start it, then run this script again." >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required (the 'docker compose' command)." >&2
  exit 2
fi
if [[ ! -f .env ]]; then
  cp .env.local.example .env
  echo "Created .env from .env.local.example. These are local-only values." >&2
fi

docker compose -f docker-compose.local.yml up --build -d
printf '\nCampusRipple local startup requested.\n'
printf 'Open: http://localhost:8000\n'
printf 'Health: http://localhost:8000/healthz\n'
printf 'Logs: docker compose -f docker-compose.local.yml logs -f web\n'
printf 'Create an administrator: docker compose -f docker-compose.local.yml exec web flask --app wsgi:app create-admin admin@localhost.test\n'
printf 'Stop: docker compose -f docker-compose.local.yml down\n'
printf 'Remove local database too: docker compose -f docker-compose.local.yml down -v\n'
