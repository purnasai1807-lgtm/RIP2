#!/usr/bin/env bash
set -euo pipefail
: "${BACKUP_FILE:?Set BACKUP_FILE to a .dump file created by backup_postgres.sh}"
: "${RESTORE_DATABASE_URL:?Set RESTORE_DATABASE_URL to a disposable empty PostgreSQL database}"
: "${SOURCE_DATABASE_URL:?Set SOURCE_DATABASE_URL to the original database URL for safety comparison}"
: "${RESTORE_CONFIRM_DISPOSABLE:?Set RESTORE_CONFIRM_DISPOSABLE=true only for a disposable restore target}"
if [[ "$RESTORE_CONFIRM_DISPOSABLE" != "true" ]]; then echo "Refusing restore: RESTORE_CONFIRM_DISPOSABLE must be exactly true" >&2; exit 3; fi
if [[ ! -f "$BACKUP_FILE" ]]; then echo "Backup file not found" >&2; exit 2; fi
# Compare normalized host/port/database identities; driver-prefix differences must not
# bypass the guard (e.g. postgresql:// vs postgresql+psycopg://).
python - "$RESTORE_DATABASE_URL" "$SOURCE_DATABASE_URL" <<'PYURL'
import sys
from urllib.parse import urlparse, unquote
def identity(value):
    p = urlparse(value.replace('postgresql+psycopg://', 'postgresql://').replace('postgresql+psycopg2://', 'postgresql://'))
    if p.scheme not in ('postgres', 'postgresql') or not p.hostname or not p.path.strip('/'):
        raise SystemExit('Refusing restore: database URLs must identify a PostgreSQL host and database.')
    return (p.hostname.lower(), p.port or 5432, unquote(p.path.lstrip('/')).lower())
try:
    if identity(sys.argv[1]) == identity(sys.argv[2]):
        raise SystemExit('Refusing to restore into the source database identity.')
except ValueError:
    raise SystemExit('Refusing restore: invalid PostgreSQL URL.')
PYURL
if [[ ! -f "$BACKUP_FILE.sha256" ]]; then
  echo "Refusing restore: backup checksum sidecar is missing." >&2
  exit 6
fi
# Require the sidecar to refer to this exact backup filename and verify it before any restore.
EXPECTED_CHECKSUM_FILE="$(basename "$BACKUP_FILE").sha256"
if ! grep -Eq "^[[:xdigit:]]{64}[[:space:]]+\*?$(printf '%s' "$EXPECTED_CHECKSUM_FILE" | sed 's/[][\.^$*+?{}|()]/\\&/g')$" "$BACKUP_FILE.sha256"; then
  echo "Refusing restore: checksum sidecar does not match the backup filename or format." >&2
  exit 6
fi
(cd "$(dirname "$BACKUP_FILE")" && sha256sum -c "$EXPECTED_CHECKSUM_FILE")
RESTORE_URL="${RESTORE_DATABASE_URL/postgresql+psycopg:/postgresql:}"
RESTORE_URL="${RESTORE_URL/postgresql+psycopg2:/postgresql:}"
SOURCE_URL="${SOURCE_DATABASE_URL/postgresql+psycopg:/postgresql:}"
SOURCE_URL="${SOURCE_URL/postgresql+psycopg2:/postgresql:}"
pg_restore --dbname="$RESTORE_URL" --no-owner --clean --if-exists --exit-on-error "$BACKUP_FILE"
TABLE_COUNT="$(psql "$RESTORE_URL" -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")"
if [[ "$TABLE_COUNT" -lt 5 ]]; then echo "Restore verification failed: only $TABLE_COUNT public tables found" >&2; exit 4; fi
# Compare critical application row counts. These checks catch a schema-only or truncated restore.
for table in '"user"' scenario impact timetable_entry; do
  source_count="$(psql "$SOURCE_URL" -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM $table")"
  restored_count="$(psql "$RESTORE_URL" -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM $table")"
  if [[ "$source_count" != "$restored_count" ]]; then
    echo "Restore verification failed: row-count mismatch for $table (source=$source_count restored=$restored_count)" >&2
    exit 5
  fi
  echo "PASS restored row count: $table = $restored_count"
done
echo "PASS backup checksum, PostgreSQL restore, schema, and critical application row-count checks."
echo "Run authenticated application-level login/workflow checks on the restored target before declaring disaster-recovery readiness."
