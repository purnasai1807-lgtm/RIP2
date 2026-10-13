# Remaining Work and Release Gates

This document distinguishes code implementation from verification requiring institutional credentials or a running staging environment. No sample/test records are official ACE Engineering College records.

## Code-level work now covered

- Multi-level impact hypotheses and record-backed evidence are labelled separately.
- Downstream evidence parent links are checked against actual prior-level activity labels; malformed levels and severity/likelihood values are bounded.
- The official timetable adapter validates provider payloads before reconciliation and uses read-only HTTPS requests, bearer-token configuration, bounded response sizes, timeouts/retries, duplicate-ID checks, and fail-closed empty-sync handling by default.
- Alternative scenario comparisons report resolved, remaining, and new impact signatures.
- Existing test modules cover app routes, authorization, CSV import validation, password reset, connector contract checks, and release preflight; dependency-light evidence tests cover impact parsing and causal-link safety.

## Must be completed before production

### 1. Full application and end-to-end tests

1. Install `requirements.txt` in a clean Python environment.
2. Run `python -m pytest -q`; fix all failures and retain the CI log.
3. Run `python -m compileall -q app migrations tests scripts` and `python scripts/validate_migration_graph.py`.
4. Against a disposable PostgreSQL database, run migrations and `python scripts/verify_postgres_guards.py` plus `python scripts/verify_postgres_concurrency.py`.
5. In staging, run authenticated browser tests with dedicated synthetic accounts for student, faculty, and coordinator/admin roles. Verify forbidden actions return 403/redirect and do not mutate data.

### 2. Impact quality against actual records

1. Obtain a reviewed, authorized, de-identified set of representative decisions and expected impacts from college stakeholders.
2. Record for each test case the input change, source record IDs, expected direct/downstream impacts, and acceptable mitigations.
3. Measure precision/recall or another agreed error metric against reviewed outcomes. Do not describe rule hypotheses as confirmed facts.
4. Test stale, missing, duplicate, contradictory, and out-of-range input data; require clear insufficiency warnings and prohibit unsupported claims.
5. Have a domain owner review each mitigation and document known false positives/false negatives.

### 3. Official college integration

- ACE Engineering College must authorize the provider endpoint, schema, token, allowed fields and reconciliation procedure; user eligibility is fixed to `@aceec.ac.in`.
- Configure `COLLEGE_DATA_API_URL` and `COLLEGE_DATA_API_TOKEN` only from the approved secret store. Do not commit credentials.
- Reconcile imported records against an official export before enabling operational decisions. Confirm deletion/update semantics with the data owner; do not infer that absent records should be deleted without approval.
- Test expired/revoked tokens, rate limits, 4xx/5xx responses, timeouts, oversized payloads, empty payloads, conflicting timetable rows, and retry recovery.

### 4. Email, deployment, and security

- Configure real SMTP credentials and an explicitly controlled test inbox; run `python scripts/verify_smtp.py` or the documented CLI probe and confirm receipt.
- Configure managed PostgreSQL, HTTPS, a unique secret key, secure cookies, `INSTITUTIONAL_EMAIL_DOMAINS=aceec.ac.in`, and platform-managed secrets.
- Apply migrations as a release step; verify health checks, log redaction, role boundaries, session behavior, rate limiting, retention approval, and audit trail access.
- Run `scripts/backup_postgres.sh`, restore to a separate disposable database using `scripts/verify_backup_restore.sh`, and record evidence of the restored row counts/checksums.
- Deploy to staging and run `scripts/smoke_test_deployment.py` plus the authenticated Playwright smoke test.

### 5. Load and release evidence

- Run Locust in staging at 50, 100, 250, and 500 simulated users, with realistic read/write mixes and a warmed database.
- Record p50/p95/p99 latency, throughput, HTTP error rate, database connection pressure, CPU, memory, and test duration for each load level.
- Set acceptance thresholds with the project owner before running tests. Do not claim 500-user capacity until measured results satisfy the thresholds.
- Run CI, review dependency/security alerts, test restore and rollback procedures, and attach the run artifacts to the release record.

## Current execution limitation

In the constrained development environment used for the latest code update, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, and psycopg were not installed and package-network access was unavailable. The dependency-light connector/evidence/preflight tests ran successfully, but the complete application test suite and services requiring PostgreSQL, SMTP, cloud credentials, or a staging URL have not been verified here.

## Latest code hardening

The application now exposes `/livez` for process liveness and retains `/healthz` as a database readiness check. Baseline browser security response headers are applied centrally; HSTS is only added when production or secure-cookie configuration is enabled. Connector regression tests cover malformed JSON, 401 fail-fast behavior, and retry after a transient 503. These changes are code-level hardening, not a substitute for a staging security review.

## JSON API acceptance

- `POST /api/v1/analyze` and `POST /api/v1/compare` are implemented as authenticated, CSRF-protected JSON endpoints. Validate them in the full Flask test suite using an authenticated session and a session-bound `X-CSRF-Token`.
- Confirm API consumers treat rule-based impacts as hypotheses, distinguish local stored records from official records, and do not treat a recommendation as an approval.
- Before exposing the API beyond the web app, define an API authentication strategy, per-client rate limits, versioning/deprecation policy, and observability requirements. The current API uses the existing session-login model; it is not a bearer-token public API.
