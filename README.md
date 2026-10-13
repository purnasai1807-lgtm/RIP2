# CampusRipple — College Decision Impact Analysis System

A full-stack web application tailored to college operations: timetable and classrooms, exams and academics, campus facilities, events and clubs, transport and attendance, and budget/procurement. It traces potential direct and downstream impacts and exports an impact report. Built with Flask, SQLAlchemy, PostgreSQL, HTML, CSS, and vanilla JavaScript.

## Data authenticity policy

This repository does not bundle fabricated college records for demos. The `seed-demo-data` command is intentionally disabled and exits without writing records. Use only ACEEC records obtained through an authorized import or official integration, and preserve source/provenance. If authorized real records are unavailable, do not claim a live-data demonstration; show the product and state the limitation. Automated unit tests may still use isolated test fixtures to verify code behavior; these are not institutional data and must never be presented as live records.

## Important product boundary

This application is a functional, rule-based decision-support system. Its default impact engine uses transparent domain rules for college-specific areas: timetable and classrooms, exams and academics, campus facilities, college events and clubs, transport and attendance, budget and procurement, and general college decisions. It does **not** claim to predict reality with certainty, and it does not automatically connect to live timetables, inventory, staffing systems, calendars, or external APIs. Review the results against actual data before making operational decisions. The code keeps impact rules in `app/engine.py` so they can be expanded or replaced with validated domain data.

## ACE Engineering College configuration and added modules

- College-branded navigation and workspace copy for ACE Engineering College.
- Role field for `student`, `faculty`, `coordinator`, and `admin`. Public registration always creates a student account; users cannot self-select elevated roles.
- CSV batch import at `/imports`, with a downloadable template at `/imports/template.csv`. Excel files should be saved as CSV UTF-8 before upload. Imports accept 1–200 scenario rows, max 1 MB, validate all rows before saving, and create drafts owned by the importing account.
- Admin user-role management at `/admin/users`. Public registration always creates a student. Provision or promote an administrator only from a trusted server shell with `flask --app wsgi:app create-admin admin@example.com`; the command prompts for a password when creating a new account. Do not make admin access depend on an email address alone.
- Coordinator/admin approval controls on a scenario detail page for submit/approve/reject status and a review note. Scenarios remain private to their owner for ordinary viewing; broader shared department workspaces and institution-wide access policy require further design before production.

## Hackathon presentation pack

The `docs/hackathon/` directory contains a judge demo runbook, pitch brief, architecture diagram, and submission acceptance checklist. Use these materials to present the current product accurately and to avoid claiming that unverified integrations or model metrics are complete. Run `python scripts/hackathon_preflight.py` before a demo to check required repository artifacts and local Python dependencies. This check is non-destructive and does not claim external production gates have passed.

## Features

- Account registration and login with Werkzeug password hashing.
- Per-user private scenarios, enforced by ownership checks on scenario routes.
- Create, edit, re-analyze, and delete decision scenarios.
- Impact chains containing direct effects and downstream levels, with causes, severity, likelihood, and suggested mitigations.
- CSV export of the decision and generated impact chain.
- Responsive, mobile-first UI using HTML templates, CSS, and vanilla JavaScript.
- CSRF tokens for POST forms, request size limits, security headers, server-side validation, and parameterized ORM queries.
- PostgreSQL via Docker Compose; SQLite fallback for local development and tests.
- Automated tests for registration, password validation, impact depth, private scenario access, and CSRF enforcement.

## Quick local launch (Docker Compose)

For a repeatable local setup with PostgreSQL, migrations, and the web service, use the local-only Compose file. This profile intentionally disables email verification and uses HTTP cookies for localhost; it is **not** a production profile.

```bash
# Linux/macOS/Git Bash
./scripts/run_local.sh

# Windows PowerShell equivalent
Copy-Item .env.local.example .env
docker compose -f docker-compose.local.yml up --build -d
```

Open `http://localhost:8000`; the database-backed health endpoint is `http://localhost:8000/healthz`. Watch startup with `docker compose -f docker-compose.local.yml logs -f web`. Create the first administrator using the command printed by `scripts/run_local.sh`, or run `docker compose -f docker-compose.local.yml exec web flask --app wsgi:app create-admin admin@localhost.test`. The CLI prompts for a password. Stop the services with `./scripts/stop_local.sh` or `docker compose -f docker-compose.local.yml down`. The database volume persists unless you explicitly run `docker compose -f docker-compose.local.yml down -v` (destructive).

The checked-in local credentials are intentionally weak and only suitable for a disposable development environment. Do not expose this profile to the internet or reuse these values in production.

See [`docs/local-development.md`](docs/local-development.md) for the repeatable Docker local setup, administrator creation, reset behavior, and test prerequisites.

## Run locally (Python)

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a unique `SECRET_KEY`. Flask does not automatically load `.env` without an additional package, so export the variables in your shell or use Docker Compose. For the easiest local start, leave `DATABASE_URL` unset to use SQLite:

```bash
# macOS/Linux
export SECRET_KEY='replace-with-a-long-random-secret'
flask --app wsgi:app run --debug
# After the server starts, provision admin in another terminal:
flask --app wsgi:app create-admin admin@example.com

# Windows PowerShell
$env:SECRET_KEY='replace-with-a-long-random-secret'
flask --app wsgi:app run --debug
# In another PowerShell window, provision admin:
flask --app wsgi:app create-admin admin@example.com
```

Open http://127.0.0.1:5000 and create an account. Do not use the development server for public production traffic.

## Run with PostgreSQL (Docker)

1. Install Docker Desktop / Docker Engine.
2. Create a `.env` file in the project root. Example (replace both values with unique secrets):

```env
POSTGRES_PASSWORD=use-a-long-unique-database-password
SECRET_KEY=use-a-long-random-application-secret-at-least-32-characters
APP_ENV=development
COOKIE_SECURE=false
```

3. Start the services:

```bash
docker compose up --build -d
```

4. Apply schema migrations as a one-off release step before starting web workers: `docker compose --profile migration run --rm migrate`.
5. Start the web service with `docker compose up --build -d web`. Open http://localhost:8000. Provision an administrator from the web container with `docker compose exec web flask --app wsgi:app create-admin admin@example.com`. Stop with `docker compose down`; persistent database data remains in the named volume. To delete that data too, use `docker compose down -v` (destructive).

For deployment behind HTTPS, set `COOKIE_SECURE=true`, configure HTTPS at the reverse proxy/platform, use managed secrets, and configure database backups. Never expose PostgreSQL publicly or commit `.env`.

## Run tests

```bash
pytest -q
```

Tests use an isolated in-memory SQLite database. A passing local test suite is not a substitute for production security review, load testing, backup/restore tests, and testing against the actual deployment environment.

## Project layout

```text
app/
  __init__.py       app factory and extensions
  models.py         User, Scenario, Impact models
  engine.py         transparent impact rules
  routes.py         authentication, scenario CRUD, analysis, CSV export
  templates/        server-rendered pages
  static/           CSS and vanilla JavaScript
 tests/              automated tests
Dockerfile
 docker-compose.yml
wsgi.py
requirements.txt
```

## Analysis logic

Each scenario has a domain, variable, current value, proposed value, and optional context. The engine selects domain-specific rules and stores each impact with a level, explanation, cause, severity, likelihood, mitigation, and source. The rule set intentionally emits multiple downstream levels for the hackathon requirement. Since user-provided context is not independently verified, the result is a structured checklist of plausible effects rather than a statistical forecast.

## Before calling this production-ready

- Run the test suite and fix any environment-specific failures.
- Add database migrations (for example, Flask-Migrate/Alembic) before schema changes; `create_all()` is suitable only for initial development.
- Configure HTTPS, strong managed secrets, database backups, monitoring/alerting, institutional email policy, SMTP delivery, and account recovery; code-level verification and database-backed login throttling are now included.
- Validate domain rules with subject-matter experts and real operational datasets; add confidence/evidence tracking and feedback loops.
- Add a durable audit trail, department-level shared scenarios, invitation/onboarding, and a complete role-based collaboration policy before multi-user institutional rollout.
- Conduct accessibility, security, and deployment reviews for the intended users and jurisdiction.


## College-focused use cases

- **Timetable & classrooms:** room/faculty clashes, practical-session changes, bus timing and syllabus recovery.
- **Exams & academics:** exam calendar conflicts, hall/invigilator availability, student preparation and evaluation timelines.
- **Campus facilities:** room/lab bookings, service interruptions, maintenance effort and learning impact.
- **College events & clubs:** venue, volunteers, equipment, participation, budgets and communications.
- **Transport & attendance:** departure mismatch, crowding, late arrivals and missed academic work.
- **Budget & procurement:** budget conflicts, supplier lead times, equipment availability and schedule impact.

The analysis rules are transparent heuristics, not an integration with a college's actual ERP, timetable, attendance, transport, or finance records. Confirm outputs with the relevant college staff before acting. Existing older domain names are retained as compatibility aliases for previously saved scenarios.

## Password recovery setup

Password recovery uses a random one-time token. Only a SHA-256 hash of the token is stored in the database; the raw token is sent by email and expires after 30 minutes. A successful reset clears the token so it cannot be reused. Unknown email addresses receive the same response as known addresses.

1. Configure `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER` in your deployment environment.
2. Set `PUBLIC_BASE_URL` to the public HTTPS URL of the deployed application. Do not leave it as localhost in production.
3. Restart the app and test a reset with a dedicated test account before enabling the feature for students.
4. Keep SMTP credentials and `SECRET_KEY` out of source control. Use the mail provider's app password where applicable.
5. Existing databases are updated with a small additive migration for the nullable reset-token columns at application startup. Back up the database before upgrading and verify startup against a copy of the production database first.

If SMTP is not configured or delivery fails, the app does not show a reset token in the browser or logs. Configure email delivery before relying on account recovery.

## Verification notes for this update

The Python source and test files compile successfully. The test suite includes password-reset checks, but could not be executed in this environment because dependencies could not be downloaded. Run `python -m pip install -r requirements.txt` and `python -m pytest -q` in your local environment, then complete an email-delivery test before production use.

## Shared college records added in this update

The College workspace is available to signed-in users at `/college-workspace`. Students can view the shared records; coordinators and administrators can add departments, course/class groups, rooms/labs, and timetable sessions. The timetable save operation rejects overlapping bookings for the same room, faculty member, or course on the same day. PostgreSQL advisory locks serialize timetable writes through this application, but the database does not yet have an exclusion constraint. Validate concurrency behavior against PostgreSQL before treating the timetable as authoritative.

Administrator-only `/admin/audit` shows recent recorded changes. The audit trail records scenario creation, updates, analysis, deletion, CSV imports, role changes, approvals, and shared college record creation. It is intended for operational traceability, not tamper-proof compliance logging. Keep the database restricted and back it up.

## Production setup checklist

- Set `SECRET_KEY` to a unique random value of at least 32 characters. Provision administrators only with `flask --app wsgi:app create-admin admin@example.com` from a trusted server shell. Never commit secrets or share them in chat.
- Set `COOKIE_SECURE=true` behind HTTPS; configure `DATABASE_URL` for PostgreSQL and use a database user with only the required permissions.
- Configure SMTP variables and `PUBLIC_BASE_URL` before relying on password recovery.
- Back up PostgreSQL before deploying changes and verify restoring the backup into a separate database.
- Run `python -m pytest -q` in an environment where the dependencies in `requirements.txt` are installed. Then perform a manual acceptance test with student, faculty, coordinator, and admin accounts.
- Do not treat the current startup `create_all()` and additive reset-field compatibility check as a complete migration framework. For a production system with evolving schema, introduce versioned Alembic/Flask-Migrate migrations and test them against a copy of the real database before rollout.
- PostgreSQL migrations install transaction-serialized overlap triggers for timetable and exam writes. SQLite relies on application checks and is intended for local development/lightweight tests; production conflict protection must be validated on PostgreSQL.

## Implemented versus not yet connected

Implemented in this codebase: user authentication and password reset flow, role-protected user administration, private decision scenarios, transparent heuristic impact chains, CSV import/export, coordinator review statuses, shared department/course/room/timetable records, basic room/faculty overlap checks, audit events, and responsive templates.

Still dependent on institutional access or production operations: a live ACE ERP/SIS connector (an approved generic read-only timetable API adapter and CSV import path now exist), official attendance identity integration, automatic room/equipment inventory synchronization, advanced what-if optimization, SMTP credentials/domain policy, actual backup-restore drills, cloud smoke tests, and measured 50–500-user load-test evidence. Email verification, database-backed login throttling, versioned migrations, and in-app notifications are implemented in code but require environment configuration and verification before production. Do not enter sensitive student records until data governance, retention, and access policies are approved.


## College operations modules

The College operations page (`/college-operations`) adds exam schedule records with active-room and room-overlap checks, campus event planning, and maintenance requests. Signed-in users may report a maintenance issue; only coordinators/admins can create official exam/event records or change maintenance status. These records are maintained in the application's database and do not synchronize with an official ACE Engineering College ERP. Invigilator allocation, exam seating plans, student attendance, equipment inventory, timetable imports, and institutional SSO remain integration work.

## Upgrade note

This update adds new SQLAlchemy models. The current app performs `db.create_all()` at startup, which creates missing tables but is **not** a replacement for versioned migrations and does not safely manage arbitrary schema changes. Back up existing data and test against a copy before upgrading. Before production rollout, add and verify Alembic/Flask-Migrate revision scripts, PostgreSQL constraint-based timetable/exam conflict protection, database backups/restores, email delivery, and load/security tests.

## Additional campus services module

The `/campus-services` page adds three database-backed areas:

- **Attendance sessions:** faculty/coordinators/admins can create and close sessions. A signed-in user can self-check-in once per session; a database unique constraint prevents duplicate records for the same user/session. Self-check-in is not identity proof or official attendance verification.
- **Equipment and supplies inventory:** coordinators/admins can add items and adjust quantities. Server validation prevents negative stock and duplicate item codes. Stock changes are audit logged.
- **Announcements:** coordinators/admins can publish messages for all users, students, or faculty with an optional expiry date.

These modules use the existing SQLAlchemy database and are created on fresh installs by `db.create_all()`. For an existing production database, take a backup and test the upgrade on a copy before rollout. The project still needs a versioned migration workflow, institutional data integration, staff-verified attendance controls, rate limiting, tested backups, and a successful full test/load/security run before it should be considered production-ready.

## Impact-chain demonstration and what-if simulations

1. Sign in and create a decision with a variable (`Date`, `Time`, `Resource`, or `Capacity`), current value, proposed value, and context.
2. Select **Run impact analysis**. The engine creates a Level 1 direct effect, Level 2 downstream effects, and Level 3 consequences where the selected domain's rules support them. Each effect shows a cause, severity, likelihood, source, and mitigation.
3. Where relevant, the analysis queries saved timetable/room/exam records. Those findings are labelled `college database evidence`; generic rules remain labelled `college rule-based` and must not be confused with verified facts.
4. Use **Try a safer alternative** to enter another proposed value. The what-if simulation displays a separate impact chain and severity summary; it does not mutate the saved proposal or live timetable.
5. Use the mitigation recommendation to pick an alternative, verify the facts with the coordinator, and separately update the official college record. A simulation never approves or publishes a real schedule.

## Versioned database migrations

New production deployments must use Alembic migrations, not automatic `create_all()` on startup. The first baseline revision is additive: it creates missing tables without dropping existing tables and adds missing password-reset columns. The next revision installs PostgreSQL triggers that serialize same-day timetable and same-date exam writes using transaction advisory locks and reject overlapping room/faculty/course bookings. A third revision adds staff verification metadata for attendance records. Existing deployments must be backed up and tested against a copy first.

```bash
# Take a restorable backup before upgrade, then apply reviewed migrations:
flask --app wsgi:app db upgrade
# Create a new reviewed migration after model changes:
flask --app wsgi:app db migrate -m "describe the schema change"
flask --app wsgi:app db upgrade
```

Do not auto-apply migrations during web-worker startup. Run them as a release step. Review generated migrations; autogenerated SQL may not include application-specific constraints or triggers.

## Official data import, attendance verification, backup and monitoring

- Coordinators/admins can import official timetable CSVs from the College workspace. Required headers are `course_code,room_code,faculty_name,day_of_week,start_time,end_time,subject`. Imports validate all rows before committing; invalid rows reject the batch. The import is a local CSV integration, not a live ACE ERP/API connection. Reconcile the source export with the college timetable owner before import.
- Student attendance check-ins are saved as `Unverified`. Faculty/coordinators/admins must explicitly mark `Present`, `Absent`, or `Rejected`; verifier identity and timestamp are retained. Self-check-in alone is not proof of attendance.
- `/healthz` checks basic database reachability and returns no secrets. Configure platform-level uptime checks and centralized log collection for production; do not expose internal exception details.
- `scripts/backup_postgres.sh` creates a custom-format PostgreSQL dump and checksum. `scripts/verify_backup_restore.sh` restores into a separate disposable database and checks that the restore contains tables. Store backups encrypted off-site and perform application-level recovery drills regularly.

## Production verification and load testing

Run `pytest -q` after installing `requirements.txt`. PostgreSQL-only trigger behavior must be tested against PostgreSQL, not SQLite. For load testing, use a separate staging environment with anonymized/synthetic data and a load generator such as Locust or k6. Measure p50/p95/p99 latency, error rates, connection-pool saturation, and database CPU/locks at 50, 100, 250, and 500 concurrent virtual users. Do not claim 500-user capacity until a measured report from the target deployment exists. External official college integrations, email delivery, production monitoring/alert routing, and a measured 500-user run still require environment-specific credentials and operational setup.

### Staged load test (not a pre-certified capacity claim)

Install Locust separately in a staging environment (`python -m pip install locust`), provision synthetic accounts, then run:

```bash
export LOAD_TEST_EMAIL='load-test-account@example.com'
export LOAD_TEST_PASSWORD='use-a-dedicated-test-password'
locust -f tests/load/locustfile.py --headless --host https://staging.example.edu --users 500 --spawn-rate 25 --run-time 10m --csv results/campusripple-500
```

Create the `results` directory first. Capture the Locust summary and server/database metrics. Run against a deployment configured like production, never a production college system or real student data. The script defines a repeatable workload; it does not itself constitute a measured result. This environment could not run it because dependencies and a staging database were unavailable.

## Additional academic workflows in this update

- **Academic services** (`/academic-services`): students/staff can submit service requests; coordinators/admins can assign and update requests. Request status changes notify the requester in-app and are audited.
- **Academic calendar**: coordinators/admins publish holidays, deadlines, academic dates, exams, and events for all users, students, or faculty. A publication creates in-app notifications for the target audience.
- **Faculty substitutions**: faculty/coordinators/admins can propose a substitute for a saved timetable session. Requests check for known timetable overlaps and require coordinator/admin review. Approval is a review record; it intentionally does not silently rewrite the official timetable.
- **Exam invigilation**: coordinators/admins assign faculty to exams; existing assignments are checked for overlapping date/time and duplicate assignments are blocked by a unique database constraint.
- **Reports and comparison** (`/reports`, `/scenarios/compare`): authorized scenario summaries, severity counts, CSV export, and side-by-side scenario comparisons.
- **In-app notifications**: each signed-in user can see their own notices and mark them read. Notification records are scoped to a recipient.

## Migration added

`20261012_04_academic_workflows.py` adds the new workflow tables additively. It does not drop tables or automatically remove existing data. Always take and verify a backup before applying a migration to an existing database.

## Verification status for the expanded modules

Python syntax compilation and Jinja template parsing were checked locally. The full Flask test suite could not be run in this execution environment because Flask and Flask-SQLAlchemy are not installed and the package index was unreachable. PostgreSQL migrations, simultaneous-write behavior, SMTP delivery, and the 500-user load test require a configured staging environment; they must not be treated as passed until run there.


## Latest implementation: email verification, official-data adapter, and deployment checks

### Email verification and SMTP

- Local demo default: `REQUIRE_EMAIL_VERIFICATION=false`; accounts can sign in without SMTP.
- Production default: verification is enabled. Set `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, and an HTTPS `PUBLIC_BASE_URL`. Production startup fails if verification is required but SMTP/safe HTTPS URL configuration is missing.
- Verification links expire after 24 hours. Password reset links expire after 30 minutes. Tokens are stored as SHA-256 digests, and email is sent only server-side.
- Test delivery to a controlled mailbox with `flask --app wsgi:app test-mail you-control@example.com`. This sends an actual email; it requires real SMTP credentials.
- Provisioned administrators are marked verified by the trusted-shell `create-admin` command. Do not put SMTP credentials in source control.

### Approved official timetable API adapter

An optional read-only connector is included at `app/integrations/college_source.py`. It deliberately does not assume ACE has a specific vendor API. Configure `COLLEGE_DATA_API_URL` (HTTPS only) and `COLLEGE_DATA_API_TOKEN` only after ACE Engineering College authorizes access and supplies a compatible API contract. The response must be JSON with a `timetable` array; see `docs/official-data-api-contract.md` for the exact fields.

Run a sync from an authorized server shell with:

```bash
flask --app wsgi:app sync-official-timetable --confirm
```

Administrators can also review sync history at `/admin/integrations` and trigger a sync there. Each batch is validated, checked for known room/faculty clashes, and committed transactionally. It records source provenance and a sync history entry. No API token is shown in the UI or logs. **Without approved credentials and a matching source API, the connector remains unconnected; CSV imports and local records remain the available data sources.**

### Deployment

`railway.json` provides a Docker-based Railway deployment profile with a pre-deploy Alembic migration, Gunicorn start command, restart policy, and `/healthz` health check. Before deploying, create a managed PostgreSQL database and set the platform variables `DATABASE_URL`, `SECRET_KEY` (32+ random characters), `APP_ENV=production`, `COOKIE_SECURE=true`, `PUBLIC_BASE_URL=https://your-real-domain`, and the SMTP variables. Keep email verification enabled in production. Configure backups and alerts in the hosting provider. Never deploy with placeholder secrets.

The app normalizes common `postgres://` / `postgresql://` URLs to the installed Psycopg 3 driver. Migration execution must complete before web traffic is shifted.

### New verification checks

- CI runs unit tests and a PostgreSQL service job that applies all migrations and executes `scripts/verify_postgres_guards.py` against the PostgreSQL conflict triggers.
- New regression tests cover email verification and fail-closed official connector configuration.
- The PostgreSQL smoke script requires a disposable test database and verifies that overlapping room bookings are rejected by database triggers. Do not run it against a production database.
- A real SMTP delivery test, approved institutional API sync, restore drill, cloud smoke test, and measured 50/100/250/500-user load run still require actual credentials and a staging environment. Configuration code does not constitute proof that those external systems work.

For a public deployment smoke check after deployment:

```bash
# Linux/macOS
CAMPUSRIPPLE_BASE_URL=https://your-staging-domain.example python scripts/smoke_test_deployment.py
# PowerShell
$env:CAMPUSRIPPLE_BASE_URL='https://your-staging-domain.example'; python scripts/smoke_test_deployment.py
```

This checks public health, landing page, and key security headers without credentials. It does not replace authenticated browser tests.


## Release preflight and migration validation

Before a deployment, run these checks from the project root:

```bash
python scripts/validate_migration_graph.py
python scripts/preflight.py
python scripts/preflight.py --check-database
python -m compileall -q app migrations tests scripts
python -m pytest -q
```

`preflight.py` checks production configuration for placeholder secrets, PostgreSQL, secure cookies, email-verification SMTP settings, HTTPS public URL, approved email domains, and consistent official API credentials. The optional database check executes `SELECT 1`. It does not send a real email, call the official college API, validate all database migrations against production data, or measure load capacity. Those checks require staging services and authorization.

For local development, set `APP_ENV=development` and, if you do not have SMTP credentials, explicitly set `REQUIRE_EMAIL_VERIFICATION=false`. For production, keep verification enabled and replace every example value with institution-approved settings.

## Latest release notes — 2026-10-12

- Added deployment preflight checks and tests for invalid/valid production configuration shapes.
- Added a static validator ensuring Alembic revisions form one linear chain without missing parents or branches.
- CI now runs migration graph validation and configuration preflight before the application tests.
- `.env.example` now enables email verification by default to reduce the chance of accidentally deploying with verification disabled. Local demo setup can explicitly turn it off.

Verification available in this build environment: Python syntax compilation, migration-graph validation, preflight unit tests (3 passed), and the standalone impact-engine demo. The full application test suite cannot be collected here because Flask is not installed and package-index DNS is unavailable. No real SMTP, official college API, PostgreSQL concurrency, restore, cloud deployment, or 500-user load test has been executed here.

## Release verification: institutional integration, SMTP, browser, concurrency, restore, and load

Do not enter live credentials into source files or commit `.env`. Configure secrets in the cloud provider's secret manager. The institutional API connector is a read-only adapter and remains inactive until ACE's authorized IT/data owner provides the approved HTTPS endpoint, bearer token, schema mapping, test records, and written permission.

### ACE ERP/SIS integration handoff

1. Obtain the approved staging API base URL and timetable endpoint, authentication method/token, response schema, stable source record ID, timezone, cancellation semantics, rate limits, and data-retention requirements from the authorized college owner.
2. Add `COLLEGE_DATA_API_URL` and `COLLEGE_DATA_API_TOKEN` as deployment secrets (URL must be HTTPS). Never use a student login/password or a browser-exposed token.
3. Deploy first to a staging environment, run a sync with synthetic or approved test records, compare row counts and representative records with the official source, inspect the integration sync history, and obtain owner sign-off before production sync.

### Real SMTP delivery test

Configure `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `MAIL_USE_TLS` or `MAIL_USE_SSL`, `PUBLIC_BASE_URL`, and the approved `INSTITUTIONAL_EMAIL_DOMAINS`. Set `SMTP_TEST_RECIPIENT` to a controlled inbox, then run `python scripts/verify_smtp.py`. This proves SMTP submission only; also test registration verification and password-reset links end-to-end on staging and confirm receipt. Use a provider app password or scoped SMTP credential, not a personal account password.

### PostgreSQL concurrency test

On a **disposable/staging PostgreSQL database only**, apply migrations, then run `python scripts/verify_postgres_guards.py` and `python scripts/verify_postgres_concurrency.py`. The concurrency script creates unique temporary records, races two overlapping room bookings, expects exactly one accepted insert, and removes its test rows. It is also run by the PostgreSQL CI job. Never point destructive/integration test scripts at the production database.

### Authenticated browser smoke test

Install the optional browser-test dependency with `python -m pip install -r requirements-browser-test.txt` and `python -m playwright install chromium`, create a dedicated synthetic account, and set `BROWSER_BASE_URL` to the HTTPS staging URL plus `BROWSER_TEST_EMAIL` and `BROWSER_TEST_PASSWORD`. Run `python tests/browser/authenticated_smoke.py`. The script signs in and checks `/dashboard`, `/college-workspace`, and `/scenarios/new` while watching for JavaScript page errors. Run this after deployment and after authentication changes; keep the account non-privileged unless the test specifically needs a coordinator/admin role.

### Backup and restore drill

Create a backup with `scripts/backup_postgres.sh`, restore it into a different, empty, disposable database using `scripts/verify_backup_restore.sh`, and compare expected business-table row counts and application login/read workflows. Keep the source and target URLs different. A successful `pg_restore`/table-count check alone is not a full disaster-recovery sign-off. Store encrypted backups off-site, restrict access, and record recovery time and recovery point.

### Measured load test

Use `tests/load/locustfile.py` only against staging with dedicated synthetic test accounts. Example:

```bash
LOAD_TEST_EMAIL='synthetic-user@example.invalid' LOAD_TEST_PASSWORD='use-a-staging-only-password' \
  locust -f tests/load/locustfile.py --headless --host https://staging.example.edu \
  --users 50 --spawn-rate 5 --run-time 5m --csv results/campusripple-50
```

Repeat at 100, 250, and 500 virtual users only after reviewing the prior run. Archive the Locust CSV/HTML report with timestamp, deployed commit, environment size, database metrics, p50/p95/p99 latency, failure rate, and connection-pool/lock observations. This repository does not claim any concurrency capacity until those measurements are captured against the actual deployment.

### Release gate

Production sign-off requires: approved API access and owner validation; a received verification email and successful link flow; production preflight plus database connectivity; PostgreSQL migration/overlap/concurrency tests; successful restore and application-level recovery checks; authenticated browser smoke tests; and a reviewed load-test report. Record any skipped test as a release blocker or explicitly accepted risk—never mark a credential-dependent test as passed without running it.

## One-command local code verification

Run `python scripts/verify_code.py` to compile Python sources, validate the migration graph, run the dependency-light tests, and execute the impact-engine demo. This command is useful in offline environments but is **not** a replacement for `python -m pytest -q` with the full dependencies installed or for the PostgreSQL, SMTP, official-data, browser, restore, deployment, and load acceptance gates. The script explicitly prints those limitations.

## Release acceptance and external integrations

Use `docs/acceptance-environments.md` for exact commands to run the full application/browser tests, PostgreSQL migration/concurrency checks, SMTP delivery test, read-only ACEEC data reconciliation preview, backup/restore drill, cloud smoke test, and Locust load test. `scripts/verify_release_acceptance.sh` runs the checks enabled by environment flags. The GitHub Actions workflow provisions disposable services for repeatable CI acceptance. It does not substitute for ACEEC-issued API credentials, real SMTP provider credentials, or access to a cloud deployment account.

## Deploying to Vercel

Vercel auto-detects the Flask app from `wsgi.py` (`app = create_app()`); `vercel.json` needs no routing. `.vercelignore` keeps tests/docs out of the bundle. If startup fails, the site shows the exact configuration error instead of a blank 500.

1. Create a managed PostgreSQL database (Neon, Supabase, etc.) and copy its **pooled** connection string.
2. Import the repo into Vercel and add these Production environment variables:
   `DATABASE_URL`, `SECRET_KEY` (32+ random chars), `APP_ENV=production`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`,
   `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`. `COOKIE_SECURE` defaults to true and `PUBLIC_BASE_URL`
   defaults to your Vercel production URL on Vercel; set `PUBLIC_BASE_URL` explicitly if you use a custom domain.
   Production requires real SMTP settings unless you deliberately set `REQUIRE_EMAIL_VERIFICATION=false`.
3. Run migrations from your machine or CI (serverless has no pre-deploy hook), then create an admin:
   ```bash
   DATABASE_URL="<url>" flask --app wsgi:app db upgrade
   DATABASE_URL="<url>" flask --app wsgi:app create-admin you@aceec.ac.in
   ```
4. Redeploy after any environment-variable change, then check `/healthz`.

On Vercel the filesystem is read-only (no SQLite) and database connections use `NullPool`.

## Phase 3: Direct impact analysis

Open an incident and select **Analyze direct impacts** to see the directly linked resource/activity, immediate dependency records, attached constraints, source references, and explicit data limitations. An authenticated JSON view is available at `/api/incidents/<incident_id>/direct-impacts`. This phase deliberately stops at one dependency edge; indirect ripple propagation is a separate phase and no operational status is automatically changed. See `docs/PHASE3_DIRECT_IMPACT_ANALYSIS.md`.


## THE RIPPLE crisis dataset (v2.2)

The supplied synthetic dataset is bundled exactly under `data/ripple_dataset/` and includes 19 CSV tables plus `incident.json` and the student glossary/rules. Sign in and open **Ripple dataset** in the navigation to see the complete table inventory, integrity validation, V1/V2/V3 service and activity impact analysis, constraints, staffing summary, repair requests, and parts availability checks. The same report is available at `/api/dataset-analysis?variant=V1` as authenticated JSON; `/dataset-download.zip` downloads the bundled source dataset. This is a read-only dataset integration and does not write synthetic rows into the operational college database.

See `DATASET_INTEGRATION_REPORT.md` for counts, results, and limitations. Impact flags are not a certified revised timetable or repair schedule; all hard constraints and human safety approvals must be checked before action.


## Phase 4 — multi-level ripple analysis

Open an incident and choose **Run ripple analysis** to trace potential consequences across multiple dependency levels. The analysis follows explicit resource/activity links, shows each causal path and source record, consolidates duplicates, prioritizes review, and suggests verification steps. It never automatically cancels an activity or changes campus status. See [`docs/PHASE4_RIPPLE_ANALYSIS.md`](docs/PHASE4_RIPPLE_ANALYSIS.md).

### Phase 5 decision intelligence

New analyses preserve a canonical input/evidence snapshot and fingerprints for reproducibility. After running an analysis, use **Verify analysis** on its detail page (or `GET /scenarios/<id>/verify-analysis`) to verify the saved inputs and results against deterministic replay. Admins can export reviewed labels from **Impact quality** for offline evaluation. Human feedback is not ground truth by itself; no model accuracy is claimed without a separately adjudicated held-out evaluation set. See `docs/PHASE5_DECISION_INTELLIGENCE.md`.

## Phase 6: Uncertainty and evidence

Phase 6 adds a scenario evidence register with source references, verification status, confidence, observation time, expiry, and notes. Unverified, disputed, stale, expired, and low-confidence records are surfaced as uncertainty impacts with validation recommendations. The evidence sensitivity action compares a hypothetical status without mutating saved evidence. See `docs/PHASE6_UNCERTAINTY_EVIDENCE.md` and apply the latest migration before use.
