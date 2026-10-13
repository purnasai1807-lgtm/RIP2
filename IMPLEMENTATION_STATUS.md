# CampusRipple implementation and verification status

## Phase 4 — multi-level ripple analysis (added)

- Authenticated incident ripple report and JSON endpoint (`/incidents/<id>/ripple-analysis`, `/api/incidents/<id>/ripple-analysis`).
- Bounded breadth-first traversal across explicit activity prerequisites; paths, source references, severity heuristic, suggested mitigations and limitations are included.
- Incident detail links into Phase 4; see `docs/PHASE4_RIPPLE_ANALYSIS.md`.
- A focused unit test covers a resource → activity → dependent activity chain and bounded depth.

## Implemented modules

- Multi-level decision impact chain with direct effects (Level 1), downstream effects (Level 2), and third-level consequences (Level 3) from transparent college-specific rules.
- Cause-and-effect explanations, severity, likelihood, mitigation, and source labels distinguishing generic rule-based hypotheses from local database evidence.
- What-if simulation results separated from saved proposals and live college records.
- Versioned Flask-Migrate/Alembic migration framework. Production schema changes are explicit release steps.
- PostgreSQL timetable/exam overlap triggers with transaction advisory locks; migration checks existing conflicts before installing guards.
- Staff-verified attendance; self-check-in remains unverified until authorized staff records a decision.
- Validated all-or-nothing timetable CSV import. Live ACE ERP/SIS integration is not configured.
- Health endpoint and basic endpoint/status/duration logging.
- PostgreSQL backup/checksum and restore-verification scripts; Locust staging workload profile.
- Campus workspace, exams, events, maintenance, inventory, announcements, and in-app service modules.
- **New in this update:** academic calendar, student/staff service requests, faculty substitution requests/reviews, invigilator allocation with conflict checks, per-user in-app notifications, aggregate reports/CSV export, and side-by-side decision scenario comparison.
- Added tests for academic services access, request creation, student authorization, reporting, and comparison pages.

## Validation performed in this environment

- Python syntax compilation: passed.
- Jinja template parsing: passed.
- Migration revision chain static check: passed.
- Independent impact-engine checks: passed for multiple levels and mitigation fields.
- Shell syntax checks and ZIP integrity: checked when packaging.
- **Full pytest suite:** not run successfully. Flask/Flask-SQLAlchemy are absent from this environment, and the package index could not be reached. Do not interpret static checks as a passing application test suite.
- PostgreSQL migrations/triggers, simultaneous-write behavior, SMTP delivery, backup restore, and 500-user load test: not executed here. Require a configured staging environment.

## Release procedure

1. Take a verified PostgreSQL backup and restore it into a disposable database.
2. Install dependencies from `requirements.txt` in a clean virtual environment.
3. Apply migrations with `flask --app wsgi:app db upgrade` as a one-off release step. In Docker Compose, use `docker compose --profile migration run --rm migrate`.
4. Review existing timetable/exam conflicts reported by migration 02; clean them up with college approval before retrying.
5. Run `python -m pytest -q` and fix every failure. Add/run integration tests against PostgreSQL, not just SQLite.
6. Verify every role boundary, calendar audience filter, service-request visibility, substitution review, and invigilator overlap using test accounts.
7. Configure SMTP, HTTPS, secrets, monitoring/alert delivery, encrypted off-site backups, and complete a restore drill.
8. Run the Locust workload in staging at 50/100/250/500 simulated users. Record p95/p99 latency, error rates, database saturation, and resource use. Do not claim 500-user capacity before measuring it.
9. Reconcile CSV-imported timetable records against an authorized official college source. No live ERP/API credentials or connector are included.

## Important limitations

This is an expanded implementation, not a certified problem-free production service. The application does not include credentials/connectors for ACE Engineering College's official ERP/SIS, transport, finance, or examination systems. Faculty substitution approval records a review but does not automatically alter the timetable. In-app notifications are implemented; production SMTP alerts and provider-based monitoring still require configuration. No measured 500-concurrent-user report exists yet.


## ACE Engineering College branding update
- Added the supplied ACE Engineering College logo at `app/static/images/ace-engineering-college-logo.png`.
- Added the logo to the global navigation, landing page, and login/registration pages.
- Added the logo as the browser favicon and included responsive sizing and accessible alternative text.


## Latest implementation update (2026-10-12)

- Fixed evidence-to-parent impact linking and added a regression test.
- Added database-backed login attempt throttling using keyed digests, with a 15-minute lockout threshold and bounded cleanup.
- The prior synthetic demo-data CLI is retained as a deprecated safety guard and now refuses to create fictional college records. The impact-report export and GitHub Actions CI workflow remain.
- `python -m compileall -q app migrations tests scripts`: passed.
- `python scripts/demo_impact_analysis.py`: passed.
- Standalone impact-engine acceptance assertions: passed.
- Full pytest suite: not run; dependency installation failed because network/DNS access is unavailable in this execution environment. Do not interpret this as a passing test suite.
- Official ACE ERP/SIS sync, configured email delivery, PostgreSQL restore test, cloud smoke test, and 50–500 user load test remain pending external access/configuration.


## Implementation update — 2026-10-12 (additional requested work)

### Implemented in code

- Configurable email verification (24-hour, hashed single-use token), institution-approved email-domain allowlist, resend throttling, and SMTP test command. Production startup refuses email-verification mode without SMTP settings, HTTPS public URL, and an approved domain allowlist.
- Generic read-only HTTPS timetable API adapter with bearer-token auth, timeouts/retries, response size/row caps, strict field validation, transaction rollback on invalid/conflicting data, source provenance, and persistent sync history.
- Admin integration status page at `/admin/integrations`, sync action, and source freshness warning when official API timetable records are older than 24 hours.
- Analysis rule version and generated timestamp persisted with each scenario; evidence references are stored per impact and included in JSON/CSV exports.
- Search/pagination for dashboard decisions, admin users, and audit events.
- Railway Docker deployment profile with pre-deploy migrations, health check, and restart policy; public deployment smoke-check script.
- PostgreSQL CI job applies migrations and exercises both timetable and exam overlap triggers against a disposable database.
- Migration revisions were made idempotent where the additive baseline can already have created current-model columns/tables on a clean database.

### Checks run in this environment

- `python -m compileall -q app migrations tests scripts`: passed.
- All Jinja templates parsed: passed.
- `railway.json` JSON syntax: passed.
- Migration graph: eight revisions, one root, no missing parent: passed.
- `python scripts/demo_impact_analysis.py`: passed.
- Shell syntax checks for backup/restore/local verification scripts: passed.
- PostgreSQL guard script and SMTP/cloud checks: not executed; no disposable PostgreSQL service, real SMTP credentials, authorized institution API, or deployment URL was supplied.
- Full pytest suite: not run successfully in this environment because Flask and Flask ecosystem dependencies are not installed and package-network access is unavailable. CI is configured to run the suite when pushed, but its outcome is not yet known.

### Remaining non-code requirements

- ACE Engineering College must approve and supply the actual API URL/schema/token and approved email domains. The generic connector is not a live ERP/SIS integration until configured and reconciled with an official export.
- Configure real SMTP app credentials, HTTPS domain, managed PostgreSQL, and platform secrets. The Railway profile is configuration only; no cloud service was provisioned or deployed from this workspace.
- Run the CI pipeline, a real backup restore drill, authenticated role-based browser tests, and Locust tests at 50/100/250/500 users in staging. Record measured results before making production or capacity claims.

## Additional implementation — impact quality feedback (2026-10-12)

- Added per-impact human review (`Confirmed`, `Incorrect`, `Uncertain`) with optional observed outcome notes.
- Reviews are unique per user and impact, retain the analysis rule version, and are included in the admin audit trail.
- Added admin impact-quality page showing review counts and latest feedback; it explicitly warns that user-reported feedback is not verified ground truth and is not model accuracy.
- Added an additive migration and regression tests for accepted/rejected feedback.
- Added `docs/data-governance-and-release-checklist.md` covering minimization, access, retention approval, release gates, prediction evaluation, and external integration boundaries.
- Static checks after this update: Python compilation passed, all 21 Jinja templates parsed, Railway JSON parsed, nine migration revisions form a single static chain, and demo engine ran successfully.
- Full pytest still could not run: dependency installation attempted but package index DNS/network was unavailable. The new routes and database migration therefore still need CI/staging execution.


## Additional release-safety update — 2026-10-12

- Added `scripts/preflight.py` to check production secret quality, PostgreSQL URL, HTTPS cookies, SMTP settings, public HTTPS URL, approved email-domain allowlist, and paired official API endpoint/token configuration. `--check-database` optionally runs `SELECT 1` and reports exception types without leaking connection strings.
- Added `scripts/validate_migration_graph.py` to check unique revision IDs, a single root, missing parents, branching, cycles, and disconnected revisions.
- Added 3 passing preflight unit tests covering placeholder production configuration, a valid configuration shape, and an incomplete official API configuration pair.
- CI runs migration graph validation and preflight checks.
- `.env.example` now enables email verification by default; local demo users without SMTP must explicitly set `REQUIRE_EMAIL_VERIFICATION=false`.
- This environment cannot install Flask dependencies because DNS/package-index access is unavailable. `python -m pytest -q` was attempted and failed during test collection with `ModuleNotFoundError: No module named 'flask'`; this is an environment blocker, not a passing full test run.


## Additional release-verification automation (2026-10-12)

- Added a PostgreSQL concurrent-writer test that races two overlapping timetable inserts and expects exactly one to succeed; wired it into the PostgreSQL CI job.
- Added a real SMTP delivery probe (`scripts/verify_smtp.py`) that requires an explicitly configured test inbox and does not print secrets. SMTP delivery has not been tested without provider credentials.
- Added an authenticated Playwright smoke test for the dashboard, college workspace, and new-scenario form. It requires an HTTPS staging deployment and a dedicated synthetic account; it has not been run against a live deployment from this environment.
- Documented the approved ACE ERP/SIS handoff, staging validation, backup restore drill, authenticated browser smoke test, and staged 50/100/250/500-user load-test release gates. Added optional browser/load-test requirements files.
- Locally revalidated migration graph, Python compilation, preflight unit tests (3 passed), and the impact-engine demo. The full app suite still cannot be collected in this environment because Flask is not installed and package-index access is unavailable. PostgreSQL, SMTP, browser-against-deployment, restore, and measured load evidence remain pending until the required staging services and credentials are supplied.


## Local-first implementation update — 2026-10-12

- Added `docker-compose.local.yml` for a local PostgreSQL + Flask deployment with database health checks, migration-on-start, and a localhost HTTP profile that does not require real SMTP or ACE credentials.
- Added `.env.local.example`, `scripts/run_local.sh`, and `scripts/stop_local.sh` to make local setup repeatable and explain administrator creation, logs, shutdown, and destructive volume removal.
- Fixed `SKIP_AUTO_SCHEMA` to honor its environment variable; this allows migration-controlled local/CI startup instead of unconditional development schema creation.
- Updated README quick-start instructions, local verification script, and CI to validate the local Compose configuration.
- Verification attempted in this workspace: compile/static checks, migration graph, preflight tests, demo engine, YAML/JSON parsing, and shell syntax. Docker is not installed here, and Flask/Flask-Migrate are not installed; therefore containers and the full Flask application tests cannot run in this workspace. These are environment limitations, not successful runtime verification.

## Verification pass — 2026-10-12 (current workspace)

Checks actually executed in this workspace:

- `python -m compileall -q app migrations tests scripts`: passed.
- `python -m pytest -q tests/test_preflight.py`: **3 passed**.
- `python scripts/validate_migration_graph.py`: passed; nine migrations form one linear chain.
- `python scripts/preflight.py`: passed for the current development environment (with the expected local-secret warning).
- `python scripts/demo_impact_analysis.py`: passed and generated four explicitly rule-based impact hypotheses over three levels.
- All 21 Jinja templates parsed successfully.
- All shell scripts passed `bash -n`; `railway.json` parsed successfully.

Environment blockers observed:

- Flask, Flask-SQLAlchemy, and psycopg are not installed in the execution environment; package network access is unavailable. Therefore the full application test suite could not be collected/run here.
- Docker is not installed, so local PostgreSQL/Docker Compose startup and database integration tests were not run.
- Playwright is installed, but the app cannot be launched without the Flask dependencies; authenticated browser tests were not run.
- No SMTP credentials, approved ACE API contract/token, deployed staging URL, or production database were provided. Email delivery, official integration, cloud smoke test, restore drill, and measured load tests remain unverified.

This record distinguishes checks that passed from external integration tests that have not been performed. No production readiness or 500-user capacity claim is made.


## Additional connector hardening — 2026-10-12

- Extracted official timetable response validation into a network-independent contract validator so it can be tested without credentials or a live provider.
- Rejects duplicate non-empty provider record IDs, malformed/overlong fields, invalid days and time intervals, non-integer/boolean capacity values, and invalid response shapes before reconciliation starts.
- Added mocked HTTP contract tests for bearer-token forwarding, timeout configuration, HTTPS enforcement, and oversized responses. All test records are explicitly synthetic.
- Official timetable sync now fails closed on a zero-row response by default, preventing a provider outage or misconfigured endpoint from being reported as a fresh successful sync. Institutions may only override this with `COLLEGE_DATA_ALLOW_EMPTY_SYNC=true` after explicitly validating that an empty response is legitimate.
- Verified in this environment: `python -m pytest -q tests/test_college_source.py tests/test_preflight.py` — **22 passed**; Python compilation passed; migration graph validation passed; preflight passed with the expected local-secret warning; deterministic impact demo ran.
- The full Flask test suite, database synchronization tests, PostgreSQL concurrency tests, SMTP, browser smoke test, restore drill, official ACE API reconciliation, deployment, and load test remain unverified because required dependencies/services/credentials are not available in this environment.

## Additional impact-chain validation update — 2026-10-12

- Hardened the analysis engine so record-backed evidence cannot claim a downstream parent that is absent from the immediately preceding impact level. Invalid evidence levels are safely downgraded to direct level rather than raising an unhandled conversion error.
- Added conservative defaults for incomplete evidence text and bounds for severity/likelihood values, avoiding malformed input being rendered as a stronger-than-supported impact.
- Added dependency-light regression tests for interval parsing, half-open interval overlap semantics, weekday matching, alternative impact comparison, invalid causal-parent correction, malformed level handling, and evidence-field bounds.
- Verification: `python -m pytest -q tests/test_evidence.py tests/test_college_source.py tests/test_preflight.py` — **29 passed**; Python compilation passed after the changes.
- Still externally blocked: complete Flask app suite (Flask ecosystem packages absent here), real PostgreSQL concurrency/migration execution, official ACE ERP/SIS access and reconciliation, real SMTP delivery, cloud staging/browser checks, restore drill, and measured load testing. These are not represented as completed.

## Additional hardening update — 2026-10-12

- Added `/livez` process liveness endpoint separate from `/healthz` database readiness probe.
- Added baseline response security headers: content-type sniffing protection, clickjacking protection, referrer policy, permissions policy, same-origin opener/resource policies, and HSTS only when production/secure-cookie configuration is enabled.
- Expanded read-only college connector tests for malformed JSON, no retry on client authentication errors, and retry after transient HTTP 503.
- Fixed Locust health task to exercise both liveness and database readiness endpoints without referencing an undefined variable.
- Verification: Python compilation passed; dependency-light test set passed (32 tests); migration graph validation passed; rule-based demo ran successfully.
- Full Flask application suite, PostgreSQL integration, browser test, SMTP delivery, cloud deployment, backup restore, and measured load test remain unverified because required dependencies/services/credentials are unavailable in this environment.

## Additional API module — 2026-10-12

- Added authenticated `POST /api/v1/analyze` for structured JSON change requests. It returns the transparent impact chain, levels/severity summary, source labels, cause/parent links, mitigations, rule version, and a statement that the analysis does not save a scenario.
- Added authenticated `POST /api/v1/compare` for baseline-versus-alternative impact comparison, including resolved/remaining/new signatures and a cautious recommendation. It does not approve or persist a decision.
- JSON writes use the same session-bound CSRF protection as browser forms via `X-CSRF-Token`; JSON content does not bypass CSRF.
- Added API validation and regression tests; documented the request contract in README.
- Verification after API changes: Python compilation passed; dependency-light tests passed (32); migration graph passed. The Flask route tests are present but still require the Flask dependencies to be installed to execute.


## Additional API coverage (2026-10-12)

- Added authenticated `GET /api/v1/meta`, `GET /api/v1/scenarios` and `GET /api/v1/scenarios/<id>` endpoints. The list endpoint supports bounded pagination and search and never lists other users' records. Scenario detail includes a structured impact chain and omits account secrets.
- API responses now use `Cache-Control: no-store` and `Pragma: no-cache`.
- Added route tests for authentication, metadata shape, pagination/privacy, impact serialization and invalid pagination. These new Flask-dependent tests compile but remain unexecuted in this environment because Flask dependencies are not installed.


## Institutional email eligibility policy (2026-10-12)
- Registration accepts only email addresses with the exact domain `@aceec.ac.in`; the check is enforced server-side and the configuration allowlist is pinned to `aceec.ac.in`.
- Login rejects non-ACE-domain accounts even if an old record exists. Email verification, verification resend, and password-reset initiation also apply the same domain eligibility rule.
- The registration form displays a short eligibility error only after an ineligible registration attempt: “Only members of ACE Engineering College are eligible to register.” The login page does not display this policy. Server-side validation remains authoritative.
- Added tests for rejection of non-college domains and attempts to override the allowlist. Full Flask-dependent tests require installing project dependencies in the local environment.

## Additional email-eligibility hardening — 2026-10-12

- Closed privileged-path gaps: the `create-admin` CLI now rejects every address outside the exact `@aceec.ac.in` domain, admin role changes refuse to manage legacy non-eligible accounts, and password-reset tokens for legacy non-eligible accounts are rejected.
- Added regression tests for CLI admin provisioning, legacy-account password-reset rejection, and domain/subdomain/lookalike edge cases.
- Static compilation and dependency-light tests are run again in this update. The complete Flask tests still require Flask dependencies, which cannot be installed in this environment because package-index DNS is unavailable.


## Registration message alignment — 2026-10-12

- Updated registration tests to assert the requested institution-wide message (students, faculty, and management are covered by “members”), without mentioning email addresses or the domain.
- Added a regression test that the login page does not expose the eligibility message or `@aceec.ac.in`.
- This change affects only the displayed registration error; exact-domain enforcement remains server-side across authentication and account-management paths.

## Verification entry point added — 2026-10-12

- Added `scripts/verify_code.py`, a repeatable one-command check for Python compilation, migration-chain validation, dependency-light regression tests, and the impact-engine demo.
- The verifier explicitly labels full Flask route testing and external service acceptance as unverified rather than converting missing dependencies into a false pass.

## Additional acceptance implementation (2026-10-12)

The repository now includes a consolidated release acceptance script (`scripts/verify_release_acceptance.sh`), an authenticated Playwright test that can either use a pre-provisioned staging account or register a one-off CI account, a read-only official-source reconciliation preview (`scripts/verify_official_integration.py`), and a backup-restore verifier that checks the archive checksum and critical application table row counts. SMTP verification supports an explicitly enabled no-auth local mail sink for CI; production SMTP still requires real provider credentials.

The GitHub Actions workflow now defines three executable acceptance jobs: full pytest/compilation/preflight checks; PostgreSQL migrations, overlap guards, concurrent writes, backup and isolated restore; and a disposable PostgreSQL-backed web app with authenticated browser checks, SMTP delivery to Mailpit, deployment health/security-header smoke checks, and a 50-user/60-second Locust regression run whose CSV results are uploaded as an artifact.

Local checks performed for this package: Python compilation passed; migration graph validation passed (9 migrations in a linear chain); dependency-light tests passed (38). Full Flask/PostgreSQL/SMTP/browser/load jobs were not run in this local container because Flask/Flask-SQLAlchemy/Flask-Login/Flask-Migrate/psycopg and Docker/PostgreSQL executables are unavailable here. GitHub Actions is configured to execute those jobs in its own provisioned environment; the job must run successfully before treating those gates as passed.

External-only blockers remain: actual ACEEC ERP/SIS access requires an authorized endpoint and token; real external email delivery requires SMTP credentials and mailbox confirmation; cloud deployment requires access to the selected cloud account and its secrets. These cannot be truthfully completed from source code alone.


## CI workflow correction — 2026-10-12

- Fixed a release-pipeline defect: CI previously invoked `scripts/demo_impact_analysis.py` without the required authorized real-data input, which necessarily exits with an error. CI now runs the reviewed impact-evaluation and evidence regression suites instead; the real-data CLI remains opt-in and fails closed when provenance/authorization is missing.
- Updated local-development and verification documentation so it no longer recommends invoking the real-data CLI without an input file.
- This correction prevents CI from fabricating institutional records and removes a guaranteed failing CI step. Full workflow execution still needs GitHub Actions to run in its provisioned environment.

## Additional implementation fixes — 2026-10-12 (follow-up)

- Fixed SMTP probe no-auth mode: missing `MAIL_USERNAME`/`MAIL_PASSWORD` no longer causes a `KeyError` when testing a local Mailpit sink.
- Added explicit SMTP mode validation: `MAIL_USE_SSL` and `MAIL_USE_TLS` cannot both be enabled. Added configurable bounded `MAIL_TIMEOUT` and support for implicit TLS (`SMTP_SSL`) in the application's mail sender.
- Added offline regression tests for conflicting SMTP modes, no-auth local sink error handling, and invalid timeouts.
- Hardened backup restore safety: restore now requires an explicit `RESTORE_CONFIRM_DISPOSABLE=true` and compares normalized PostgreSQL host/port/database identities rather than comparing URL strings, preventing driver-prefix differences from bypassing the source-target guard.
- Corrected CI database creation to use an explicit `CREATE DATABASE` command through the PostgreSQL maintenance connection instead of passing a connection URL as a positional `createdb` database name.
- Verification: `python scripts/verify_code.py` — **41 tests passed** (dependency-light set); Python compilation passed; nine-migration graph passed; GitHub Actions YAML parsed and contains three jobs; backup/restore shell scripts pass `bash -n`.
- Full Flask/PostgreSQL/browser/load pipeline could not be executed locally: Flask/SQLAlchemy/Flask-Migrate/psycopg/Locust are absent and package-index DNS is unavailable. These remain CI execution gates, not claimed passes. External SMTP delivery, ACEEC API reconciliation, and cloud deployment still require authorized provider access and configuration.

## Additional restore-safety hardening — 2026-10-12

- The restore verifier now refuses to restore a backup unless its SHA-256 sidecar exists, uses the expected filename/format, and validates successfully before `pg_restore` is invoked.
- Added dependency-light subprocess tests for same-database refusal across PostgreSQL driver-prefix variants, explicit disposable-target confirmation, missing checksum refusal, and tampered-backup detection.
- These checks do not replace a live PostgreSQL restore drill; the live restore remains an integration acceptance gate.

## Phase 5 — decision intelligence and reproducibility (2026-10-13)

- Persisted canonical input/evidence snapshots plus SHA-256 input and output fingerprints for new analysis runs.
- Added authorized reproducibility verification endpoint (`GET /scenarios/<id>/verify-analysis`) that checks snapshot integrity, saved output integrity, and deterministic replay against the same captured evidence.
- Added fingerprints and snapshot availability to JSON exports and fingerprints to the scenario analysis header.
- Added admin-only labeled feedback CSV export for offline evaluation. Quality reporting explicitly distinguishes user feedback from independently verified ground truth and does not claim unmeasured accuracy.
- Added migration `20261013_12_analysis_reproducibility.py` and Phase 5 evaluation protocol documentation.
- Checks performed: compileall passed; 28 Jinja templates parsed; migration chain has 12 revisions and one linear root; focused tests passed (18 passed).
- Full Flask application tests, database migration execution, browser end-to-end verification, and production integration tests remain unverified because Flask is not installed in the authoring environment. Run migrations and the full test suite in the configured runtime before production use.
