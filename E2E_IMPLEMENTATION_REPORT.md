# CampusRipple E2E and authorization hardening report

## Implemented in this update

- Fixed three authorization regression tests that previously submitted POST requests without the application's required CSRF token. These tests now provide a valid session token so their assertions reach the intended role/ownership authorization logic instead of being stopped by CSRF validation.
- Expanded scenario-ownership regression coverage to assert another student cannot read, edit, analyze, simulate, delete, or export a private scenario and that denied writes leave the stored scenario unchanged.
- Added role-matrix tests for admin-only read routes across student, faculty, coordinator, and admin accounts.
- Added role-matrix testing for department management, verifying only coordinator/admin can pass the role gate and invalid test input does not create data.
- Added dependency-light static route-policy checks in `tests/test_route_authorization_static.py`. These verify that every declared route is explicitly public or has `@login_required`, privileged routes contain role checks, admin-only routes explicitly require `admin`, private scenario handlers retain ownership checks, and the global POST CSRF guard remains present.
- Updated `scripts/verify_code.py` to run the new static authorization checks even when Flask dependencies are not installed.
- Added `pytest.ini` to standardize test discovery and repository-root import resolution.
- Added `docs/authorization-e2e-test-matrix.md` with staging acceptance steps.

## Checks executed in this environment

- `python scripts/verify_code.py`: PASS.
- Dependency-light pytest suite: **49 passed** (includes the 4 new static route-policy checks).
- Python syntax compilation via `compileall`: PASS.
- Migration graph validator: PASS; 9 revisions form one linear chain.

## Tests authored but not executed here

The new/updated runtime Flask authorization tests in `tests/test_app.py` are included in the source package and compile successfully, but were not run in this environment because Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, and psycopg are unavailable and package-index DNS resolution failed during installation. Run `python -m pip install -r requirements.txt` and `python -m pytest -q` in a connected development/CI environment to execute them.

## Still not verified

- Full Flask route suite and browser E2E acceptance.
- PostgreSQL migrations, overlap guards, concurrency, and database-backed role checks.
- Actual SMTP delivery, official ACEEC ERP/SIS reconciliation, live deployment, backup/restore drill, and measured load capacity.
- No official college data or credentials were added. No production deployment or remote GitHub repository was modified.
