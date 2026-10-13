# CampusRipple — implementation plan and verification checklist

This plan preserves the Flask/SQLAlchemy architecture and the ACE Engineering College logo/branding. It distinguishes code already present from work that needs real credentials, deployment infrastructure, or institutional approval.

## Current baseline from repository inspection

- Flask app factory, SQLAlchemy models, Flask-Migrate migrations, Jinja templates, CSS/JS, PostgreSQL Docker Compose, health endpoint, backup scripts, Locust profile, and a pytest suite exist.
- The product already includes authentication, role-based routes, private decision scenarios, rule-based impact chains, CSV import/export, college workspace data, academic workflows, in-app notifications, reports, and ACE branding.
- The source's `IMPLEMENTATION_STATUS.md` explicitly says the full pytest suite, PostgreSQL concurrency tests, SMTP delivery, backup restore, and 500-user load test have not been completed in its original validation environment.
- No authorized ACE ERP/SIS credentials or API contract are included. Do not simulate a live integration or claim official data is connected.

## Phase 0 — Establish a reproducible baseline (first)

1. Create a clean Python 3.12 virtual environment (the Dockerfile uses Python 3.12).
2. Install `requirements.txt`; run `python -m pytest -q` and record all failures.
3. Run `python -m compileall -q app migrations tests` and check `docker compose config` with a configured `.env`.
4. Keep a copy of the original ZIP and use version control before changing schemas or business logic.
5. Treat a missing dependency or unavailable PostgreSQL/SMTP service as an environment limitation, not a passing test.

Acceptance: a repeatable setup guide, test output saved in CI, and no unreviewed database migration applied to production.

## Phase 1 — Security and identity

1. Keep public registration limited to the `student` role; continue provisioning admins from a trusted shell.
2. Enforce HTTPS-only secure session cookies in production. New startup validation rejects a production configuration with `COOKIE_SECURE` disabled.
3. Retain CSRF validation, password hashing, request-size limits, safe generic password-reset responses, and per-user scenario ownership checks.
4. Verify every read/write route for student, faculty, coordinator, and admin using both allowed and forbidden test cases.
5. Add email verification before institutional accounts receive trusted-data permissions; use an institution-approved email/domain policy rather than trusting a typed address alone.
6. Add login/reset throttling backed by a shared store before scaling to multiple workers; in-memory-only limits are not sufficient for a multi-instance deployment.
7. Add dependency scanning, secret scanning, and a documented security incident/contact process.

Acceptance: role-matrix tests pass, no user can promote their own role, private records stay private, and production refuses unsafe cookie configuration.

## Phase 2 — Data integrity and database operations

1. Use PostgreSQL for staging and production. SQLite is for local development and lightweight tests only.
2. Review all Alembic migrations and apply them as a one-off release step after a verified backup; never run `create_all()` as a production migration strategy.
3. Exercise timetable/exam conflict guards with overlapping and non-overlapping inserts, including concurrent transactions.
4. Add foreign-key, uniqueness, input-range, and status-transition tests for every academic workflow.
5. Run the supplied backup script, restore into a disposable database, and verify counts and application startup before accepting the backup process.
6. Document retention, deletion, export permissions, and who may view each category of student/faculty data.

Acceptance: PostgreSQL integration suite passes, migrations work from a clean database and from the previous release, and a restore drill is recorded.

## Phase 3 — Complete the user workflows

1. Create a role/route inventory and make navigation match the user's role.
2. Student: view published academic calendar/timetable, submit service requests, view only their own request statuses and notifications, and track their own decision scenarios.
3. Faculty: view assigned classes, submit substitution requests, and receive relevant announcements; do not expose unrelated student data.
4. Coordinator: manage department/course/room records, review requests, allocate invigilators, and see conflicts before saving.
5. Admin: manage roles, review audit events, export aggregate reports, and monitor system health. Protect destructive actions with confirmation and audit entries.
6. Add pagination and search to growing tables; keep exports permission-checked and bounded.
7. Ensure approvals record reviewer, time, status, and note. A substitution approval must not silently rewrite an official timetable until an approved workflow is designed.

Acceptance: browser-level happy-path tests cover each role, invalid transitions are rejected, and each write produces the expected audit event.

## Phase 4 — Official data and integrations

1. Obtain an authorized data contract and access approval from ACE Engineering College before integrating an ERP/SIS.
2. Build an adapter interface for timetable, rooms, courses, staff assignments, attendance, and examination calendar. Keep provider-specific API code outside route handlers.
3. Start with read-only sync, validate imported rows, store source/provenance and sync timestamps, and surface stale-data warnings.
4. Reconcile CSV imports with a trusted official export before treating the data as operational truth.
5. Configure SMTP using provider app credentials; test success, failure, retry, and password-reset expiry in staging.
6. Use idempotency keys and retry policies for external calls; never log tokens, passwords, or sensitive query parameters.

Acceptance: authorized integration tests with sandbox/approved credentials, reconciliation report, and documented failure/recovery behavior. Without credentials this phase remains unconnected by design.

## Phase 5 — Decision intelligence

1. Keep current rules explainable and label rule-based consequences as hypotheses, not verified facts.
2. Add structured evidence links from actual college records to each impact; distinguish observed conflict, deterministic rule, and speculative downstream consequence.
3. Store model/rule version, inputs, generated-at timestamp, and evidence identifiers with each analysis.
4. Add human review, feedback capture, and offline evaluation before introducing a trained prediction model.
5. Report precision/recall or calibration only when measured against a labeled historical dataset; never fabricate accuracy figures.
6. Keep simulations separate from official records until a reviewer explicitly approves a change.

Acceptance: impact explanations are reproducible, evidence is traceable, and any model is evaluated on a held-out dataset before operational use.

## Phase 6 — Deployment, observability, and scale

1. Local: use a virtual environment or Docker Compose; verify `/healthz` and the core flows.
2. Cloud: use a managed PostgreSQL database, platform secret manager, HTTPS, `COOKIE_SECURE=true`, and the existing Gunicorn entry point (`wsgi:app`).
3. Run migrations as a release job before shifting traffic. Do not run migrations independently from every web worker.
4. Configure SMTP, uptime/error monitoring, structured logs, alert routing, and encrypted off-site backups.
5. Set database connection pool and Gunicorn worker counts based on measured memory/connection budgets.
6. Run Locust at 50, 100, 250, and 500 simulated users in staging. Record p50/p95/p99 latency, error rate, throughput, CPU/memory, and DB saturation; tune from evidence.
7. Add CI for compile, tests, migration checks, dependency scanning, and a small PostgreSQL integration job.

Acceptance: documented rollback, successful restore drill, no critical/high unresolved security findings, and a measured load report. Do not claim 500-user capacity until the test passes on the intended deployment tier.

## Suggested cloud release sequence

1. Provision managed PostgreSQL and an application service.
2. Set `SECRET_KEY` (at least 32 random characters), `APP_ENV=production`, `COOKIE_SECURE=true`, and the provider-issued `DATABASE_URL` in the secret manager.
3. Configure SMTP and `PUBLIC_BASE_URL` only when available; verify outbound email from staging.
4. Back up the database, run `flask --app wsgi:app db upgrade` once, then deploy the web process using `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60` (adjust to provider requirements).
5. Create/promote the initial admin through a secure one-off shell command; never use a public registration form to create an admin.
6. Smoke-test `/healthz`, registration/login, CSRF rejection, role restrictions, scenario create/view/delete, CSV import/export, academic requests, and notification visibility.
7. Verify logs contain no credentials or reset tokens; verify backups and alerting before opening access to users.

## Code changes in this update

- Production startup now fails fast when secure session cookies are disabled. Production must be served over HTTPS with `COOKIE_SECURE=true`.
- Added a restrictive `Permissions-Policy` response header and HSTS only when secure cookies are enabled.
- Cleaned the duplicate `COOKIE_SECURE` declaration in `.env.example` and clarified local versus production values.
- Added this plan as a maintained, acceptance-oriented implementation checklist.

## Verification record for this update

- The ZIP was extracted and repository files inspected.
- `pytest -q` was attempted but collection stopped because Flask is not installed in the current execution environment (`ModuleNotFoundError: No module named 'flask'`). Therefore application tests are **not verified as passing**.
- Next verification: install `requirements.txt` in a clean Python 3.12 environment, then run the full test and PostgreSQL integration steps above.

## Challenge acceptance mapping — Decision Impact Analysis

- **Proposed change input:** the scenario form captures a domain, variable (date/time/resource/capacity and related fields), current value, proposed value, and context.
- **Direct impact:** `app/engine.py` labels level 1 as a possible direct impact. `collect_impact_evidence()` in `app/routes.py` adds observed facts only when matching local records can be identified.
- **Two downstream levels:** the engine emits level 2 and level 3 consequences for supported domain rules. Each rule-based downstream item is labeled as a hypothesis and has a `parent_activity` that identifies its causal predecessor. Parent links are assigned across the previous level rather than all pointing at one arbitrary final item.
- **Cause-and-effect:** each impact displays its predecessor and a cause explanation in `scenario_detail.html`; the source field distinguishes rule hypotheses from database evidence.
- **Summary and mitigation:** the scenario detail page counts impacts by level and severity, and every impact includes a mitigation suggestion. The what-if simulation compares an alternative without overwriting the saved proposal.
- **Demonstration:** run `python scripts/demo_impact_analysis.py` from the project root after installing dependencies (the script itself only imports the local engine module). This is a deterministic rules demo, not proof of a live ERP integration.

Acceptance checks: `python -m pytest -q`; run `python scripts/demo_impact_analysis.py <authorized-real-input.json>` only with authorized real data; create a scenario in the UI; run analysis; verify levels 1, 2 and 3, parent/cause text, at least one mitigation, and alternative simulation. For a real-data demonstration, seed approved sample room/timetable records and verify that evidence is explicitly labeled as database-backed. Do not claim real-world conflict detection for free-text values that cannot be matched to a specific record.


## Additional implementation work in the latest update

- Fixed evidence-backed impact parent assignment so level-2/3 evidence does not reference an undefined variable and is linked to a prior-level activity when one exists.
- Added persistent login throttling backed by the application database. It stores keyed digests rather than raw email/IP identifiers, rejects sign-in attempts after eight recent failures in a 15-minute window, and prunes old attempt records. If the app is behind a proxy, only enable `TRUST_PROXY_HEADERS` when the proxy strips client-supplied forwarding headers and sets its own trusted value.
- The `seed-demo-data` command is retained only as a safety guard and now refuses to create fictional college records. Use only authorized institutional records; none are bundled.
- Added per-scenario JSON export with the proposed change, summary, cause/effect links, mitigation, source provenance, and an explicit uncertainty note. CSV export remains available.
- Added a GitHub Actions workflow for Python 3.12 compile checks, pytest, and the deterministic impact-engine demo. CI will run when pushed to GitHub; it has not run in this environment.

## Remaining institution / deployment prerequisites

- Live ERP/SIS integration cannot be truthfully completed until ACE Engineering College authorizes access and supplies its API/data contract and credentials. The current local workspace and CSV import are the supported data sources.
- Email verification and SMTP delivery require an institution-approved email/domain policy and configured mail credentials. Password reset safely degrades to a generic response if email delivery is not configured.
- Cloud infrastructure, PostgreSQL migrations, backup restore, and load tests must be run in the actual target environment. This environment has no network access to install the Python dependencies, so the full Flask pytest suite could not be executed here.


## Additional completion pass — code delivered, external verification still required

- Added optional email verification and an institution-approved email-domain allowlist; SMTP settings are validated at production startup, and `test-mail` verifies a real provider configuration when credentials are supplied.
- Added a generic read-only HTTPS timetable source adapter, an admin integration status/sync page, transactional conflict validation, source provenance, sync history, and stale-data warnings. It cannot connect to ACE's real ERP/SIS until the college authorizes and provides its API contract and credentials.
- Added rule-version/analyzed-at metadata and per-impact evidence references; included provenance in exports.
- Added dashboard/admin user/audit search and pagination.
- Added Railway deployment configuration, deployment smoke-test script, and PostgreSQL CI integration tests for both timetable and exam overlap guards.
- Static syntax, templates, migration graph, demo engine, shell syntax, and ZIP integrity checks passed locally. The full Flask pytest suite and external integration tests remain unverified because the runtime lacks Flask dependencies and package network access. No cloud service, SMTP account, or official college API was available to provision.
