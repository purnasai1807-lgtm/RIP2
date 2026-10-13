# Phase 8 — Operational Readiness, Observability & Recovery

Phase 8 adds a minimal, secret-safe operational layer to CampusRipple.

## Features

- `GET /livez`: lightweight liveness probe that does not depend on the database.
- `GET /health/ready`: readiness probe that checks database connectivity and the required bundled Ripple dataset files. It returns HTTP 200 when ready and HTTP 503 when a required dependency is unhealthy; it never returns credentials or exception details.
- `GET /admin/system-readiness`: authenticated admin-only diagnostics for database connectivity, dataset validation, decision CSV schema, email configuration, and secure session-cookie configuration.
- Recovery checklist for verified backups, disposable restore targets, migrations, test runs, and staged workflow checks.
- Adds the System readiness link to the admin navigation.

## Configuration

No new environment variables or database tables are required. Existing `DATABASE_URL`, `DECISIONS_CSV_PATH`, `MAIL_SERVER`, `MAIL_DEFAULT_SENDER`, `APP_ENV`, and `COOKIE_SECURE` settings are inspected without displaying secret values.

## Operational limitations

Readiness checks are diagnostic, not a substitute for a real backup/restore drill. SMTP configuration is checked but email delivery is not tested by this page. The application does not automatically restore a production database. Recovery remains an explicit operator action against a verified disposable target.

## Verification

Run `python -m pytest -q` in the project's configured virtual environment, then check `/livez`, `/health/ready`, and `/admin/system-readiness` in a staging deployment. A release should not be considered production-ready until the complete test suite and browser workflows pass against the configured database.
