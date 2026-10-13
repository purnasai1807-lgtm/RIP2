# Acceptance environments and execution guide

This repository now has executable acceptance paths for application/browser behavior, PostgreSQL migrations and concurrent writes, SMTP, official-source reconciliation preview, backup restoration, deployment smoke checks, and load measurements. A script existing in the repository is not proof that an external service has passed; retain actual run logs and artifacts.

## 1. Full application and authenticated browser acceptance

In a clean environment install `requirements.txt` and run `python -m pytest -q`. CI runs the full pytest suite. The `browser-smtp-load` CI job starts a disposable PostgreSQL-backed application, registers a dedicated synthetic `@aceec.ac.in` test user through the UI, checks dashboard/workspace/scenario/report routes, and verifies a student cannot open `/admin/users`. The CI registration flag must never be enabled against production. For staging, use an already provisioned test account and an HTTPS `BROWSER_BASE_URL`:

```bash
pip install -r requirements-browser-test.txt
python -m playwright install chromium
BROWSER_BASE_URL=https://staging.example.edu \
BROWSER_TEST_EMAIL=dedicated-test-account@aceec.ac.in \
BROWSER_TEST_PASSWORD='from-secret-store' \
python tests/browser/authenticated_smoke.py
```

Run separate accounts and test cases for faculty, coordinator, and admin roles before release; the included browser smoke specifically verifies the student boundary and basic authenticated routes.

## 2. PostgreSQL migration and concurrent-write tests

On a disposable PostgreSQL database, set `DATABASE_URL`, `SECRET_KEY`, and `SKIP_AUTO_SCHEMA=true`, then run:

```bash
flask --app wsgi:app db upgrade
python scripts/verify_postgres_guards.py
python scripts/verify_postgres_concurrency.py
```

CI provisions PostgreSQL 16 and runs these tests on each push/PR. The concurrency test writes uniquely named temporary rows and cleans them up. Do not point it at a production database.

## 3. SMTP delivery

The CI pipeline sends both a direct SMTP probe and an application-generated test email to Mailpit, a local mail sink; this verifies SMTP protocol and application mail wiring without sending to real people. For real delivery, configure SMTP host, port, TLS mode, username, app password, sender, and a controlled test recipient in the deployment secret store. Then run `python scripts/verify_smtp.py` and `flask --app wsgi:app test-mail controlled-inbox@aceec.ac.in`; verify actual receipt, headers, and spam placement. Real-provider delivery cannot be completed from this repository without provider credentials and mailbox access.

## 4. Authorized ACEEC ERP/SIS connection and reconciliation

Only use the official endpoint/schema and read-only API token issued by ACE Engineering College. Configure `COLLEGE_DATA_API_URL` and `COLLEGE_DATA_API_TOKEN` through a secret store. Run the read-only preview first:

```bash
python scripts/verify_official_integration.py
```

It validates the response contract and reports stable-ID matches/new/absent counts plus local department/course/room reference gaps; it does not mutate data. Have the data owner review the report. Only then run `flask --app wsgi:app sync-official-timetable --confirm` in an approved maintenance window. The connector is read-only to the upstream source; local reconciliation is transactional and fails on conflicts. Do not delete local records merely because they are absent upstream without written data-owner approval. This cannot pass until ACEEC supplies an authorized endpoint and token.

## 5. Backup restoration

`backup_postgres.sh` produces a custom-format PostgreSQL backup and SHA-256 checksum. `verify_backup_restore.sh` refuses to restore to the exact source URL and requires a separate disposable target. The CI PostgreSQL job creates a backup and restores it to a different database. For production operations, retain encrypted off-site backups and run a restore drill in an isolated environment; record source/restore database identity, checksum, critical-table row counts, and application login/read checks. Never test destructive restoration against the production database.

## 6. Cloud deployment and smoke test

`Dockerfile`, `railway.json`, and the Compose files describe deployment and migration startup. The repository cannot deploy to an account it cannot access. Create a staging service and managed PostgreSQL instance in the selected cloud, configure secrets, HTTPS/custom domain, SMTP, backups, and monitoring, then run:

```bash
CAMPUSRIPPLE_BASE_URL=https://your-staging-host.example python scripts/smoke_test_deployment.py
BROWSER_BASE_URL=https://your-staging-host.example BROWSER_TEST_EMAIL=... BROWSER_TEST_PASSWORD=... python tests/browser/authenticated_smoke.py
```

Do not use placeholders in production secrets. Keep database migrations as a release step and confirm `/healthz`, `/livez`, HSTS, TLS, log redaction, rollback, and restore behavior.

## 7. Measured load test

Install `requirements-load-test.txt`; use a staging URL and a dedicated account with no production privileges:

```bash
LOAD_TEST_EMAIL=dedicated-test-account@aceec.ac.in \
LOAD_TEST_PASSWORD='from-secret-store' \
locust -f tests/load/locustfile.py --headless -H https://staging.example.edu \
  --users 50 --spawn-rate 5 --run-time 5m --csv results/campusripple
```

CI also runs a 50-user, 60-second test against its disposable app and uploads Locust CSV results. This is a regression signal, not a production capacity claim. Before release, run 50/100/250/500 user profiles in staging and record p50/p95/p99 latency, throughput, error rate, CPU/memory, and database pool pressure; agree acceptance thresholds with the project owner first.
