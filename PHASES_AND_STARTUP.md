# THE RIPPLE (ripple111): phases and startup

## Phase coverage in this codebase

1. **Campus data model** — campus entities, resources, activities, dependencies, timetable, exams, facilities and data provenance.
2. **Incident input and detection** — incident records and updates, dataset validation/import, incident workflows.
3. **Direct impact analysis** — transparent first-order impact rules, evidence labels and mitigation suggestions.
4. **Ripple analysis** — bounded multi-level dependency traversal with paths, causes and caveats.
5. **Decision intelligence** — what-if scenario analysis, comparison of alternatives, priority scoring and reports.
6. **Uncertainty and evidence** — evidence references, source/provenance labels, input-quality checks and bounded severity/likelihood.
7. **Mitigation and recovery** — mitigation actions, service requests and operational review workflows.
8. **Operational readiness** — health checks, migration tooling, backup/restore and release preflight scripts.
9. **Outcome review and feedback** — impact feedback and scenario outcome review records.

Related feature areas include authentication and role checks, scenario CRUD, CSV import/export, academic calendar, service requests, faculty substitutions, invigilator allocation, notifications, integration configuration, and authenticated JSON endpoints. See `README.md`, `IMPLEMENTATION_STATUS.md`, and `docs/` for detail.

## Windows quick start

1. Install Python 3.11 or newer.
2. Extract the ZIP so the `ripple111` folder remains intact.
3. Double-click `START_RIPPLE111.bat`. It creates a virtual environment, installs packages, checks Python syntax, and starts the local server. Internet access is required for the first package installation.
4. Open `http://127.0.0.1:5000` if the browser does not open automatically.
5. Register using an `@aceec.ac.in` address for institutional-policy-compatible use. The `@localhost.test` address is allowed only in non-production mode for local development/admin bootstrap.
6. Use `Ctrl+C` in the terminal to stop the server.

## macOS/Linux quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export APP_ENV=development
export COOKIE_SECURE=false
export SECRET_KEY='replace-with-a-long-random-local-secret'
flask --app wsgi:app run --host 127.0.0.1 --port 5000
```

## Verification boundary

A working local web deployment requires installing the packages in `requirements.txt`. This environment could not reach the Python package index, so full Flask runtime tests could not be executed here. Python compilation and the migration graph were checked. Official ACE ERP/SIS access, SMTP, PostgreSQL concurrency, browser acceptance, backup restore, and load capacity still require credentials or services and must not be represented as verified. Rule-based impacts are decision-support hypotheses, not confirmed real-world outcomes.
