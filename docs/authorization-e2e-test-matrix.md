# Authorization E2E Regression Matrix

This matrix is intended to run against the Flask test client and, separately, a staging deployment using synthetic accounts. It does not claim a test passed unless it was executed.

## Added automated regressions

`tests/test_app.py` now includes:

- `test_non_owner_cannot_read_edit_analyze_simulate_delete_or_export_scenario`: verifies a second student receives a concealed `404` for another student's scenario across detail, edit, analyze, simulate, delete, CSV export, and JSON export; then checks denied operations did not mutate or delete the record.
- `test_student_cannot_change_another_users_role`: verifies a student cannot use the admin role-change endpoint and the target role remains unchanged.
- `test_coordinator_can_approve_but_cannot_edit_non_owned_scenario`: verifies a coordinator can use the explicit approval workflow but cannot edit a scenario they do not own.

These tests use synthetic in-memory test data only. They do not connect to ACE Engineering College systems. POST-based authorization tests must send a valid CSRF token so a 400 CSRF response cannot incorrectly stand in for a 403 authorization denial.

A dependency-light static policy audit now runs from `scripts/verify_code.py`. It checks that every route is explicitly public or protected by `@login_required`, key privileged routes call `require_roles`, admin-only routes explicitly name the admin role, sensitive scenario routes retain ownership checks, and the global POST CSRF guard remains in place. Static source checks supplement but do not replace live route execution.

## Run locally

From the `decision-impact-system` repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

`pytest.ini` sets `pythonpath = .` so both `pytest` and `python -m pytest` resolve the repository modules consistently when run from the project root.

## Staging checks still required

Use dedicated synthetic accounts and a disposable/staging database. Verify:

- student, faculty, coordinator, and admin permissions across every protected page and API;
- CSRF failures on all state-changing browser requests;
- session invalidation after logout, password reset, and role downgrade;
- unauthorized attempts leave persistent data unchanged;
- direct URL, CSV/JSON export, pagination, and API object-ID tampering;
- PostgreSQL constraints and concurrency behavior.

Do not run destructive or concurrency tests against production data.
