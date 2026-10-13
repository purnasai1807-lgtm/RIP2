#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?Set DATABASE_URL to the PostgreSQL connection URL}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/campusripple-$STAMP.dump"
# pg_dump custom format supports selective and full restore. Keep backups encrypted at rest.
PG_DUMP_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
PG_DUMP_URL="${PG_DUMP_URL/postgresql+psycopg2:/postgresql:}"
pg_dump --dbname="$PG_DUMP_URL" --format=custom --no-owner --file="$OUT"
pg_restore --list "$OUT" >/dev/null
sha256sum "$OUT" > "$OUT.sha256"
echo "Backup created and archive-validated: $OUT"
echo "Store the file and checksum in encrypted off-site storage; this script does not upload it."
