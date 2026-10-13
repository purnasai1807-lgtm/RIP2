# Phase 1 — Campus Data Model

## Delivered
- Campus activities with unique codes, type, location, expected attendance, criticality, status, optional start/end times, and notes.
- Shared resources with unique codes, type, location, capacity, availability status, and notes.
- Directed activity dependencies targeting exactly one resource or another activity, with relationship type, importance, and explanation.
- Resource constraints with operator, limit, unit, hard/soft classification, and notes.
- Authenticated read access and coordinator/admin-only create/delete operations.
- CSRF-protected mutations, audit events, validation of enumerated fields, duplicate-code handling, time-range validation, and dependency/constraint cleanup on deletion.
- Alembic migration `20261013_10_campus_data_model.py`.

## Deploy / verify
1. Back up the production database before migration.
2. Run `flask --app wsgi:app db upgrade` in the configured deployment environment.
3. Sign in as a coordinator/admin and open `/campus-model`.
4. Add one activity, one resource, one dependency, and one constraint; confirm each appears in the lists.
5. Try a duplicate code, an invalid time range, and a self-dependency; each should be rejected.
6. Delete test records and verify dependent links/constraints are removed.
7. Run `python scripts/verify_code.py` and `python -m pytest -q` in an environment with `requirements.txt` installed.

## Boundaries
No real institutional records are seeded because campus schedules, capacities, staff and equipment must come from authorized, verified data. The packaging environment did not have Flask installed and could not verify a live PostgreSQL migration, browser workflows, or production deployment. Do not mark production acceptance complete until those environment-dependent checks pass.


## Phase 1 completion notes (ripple111)

The campus data model supports create, read, update, and delete workflows for activities and resources; dependency and resource-constraint records can be created, listed, and deleted. All mutations require coordinator/admin role and use the application's session CSRF protection. Activity/resource edits are audited. Dependency creation validates enumerated values, prevents self-dependencies, and rejects directed cycles in activity-to-activity dependencies. Database uniqueness and check constraints remain the final integrity guard.

Before production sign-off, install `requirements.txt`, run the full pytest suite against a test database, apply `flask --app wsgi:app db upgrade` to a staging PostgreSQL database, and exercise create/edit/delete flows with coordinator, admin, and read-only accounts. Real campus data must be entered or imported from an authorized source; this project does not fabricate institution records.
