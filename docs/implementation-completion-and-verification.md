# Decision Impact Analysis implementation and verification notes

## What this revision adds

- Conservative evidence checks for timetable resource, time and capacity changes.
- Time intervals are parsed only from unambiguous `HH:MM` or `HH:MM-HH:MM` values. Overlap checks use half-open intervals, so a session ending at 11:00 does not overlap one starting at 11:00.
- A time check requires a matching session identifier in the scenario context. It checks the candidate session against saved records for shared room or faculty and reports the exact timetable-entry reference.
- Unknown room/session identifiers, missing day/time, missing records, and stale official snapshots are explicitly reported as insufficient data or data-quality warnings. They are not represented as confirmed conflicts.
- Capacity checks require a room identifier and numeric proposed capacity. The result explicitly says that a capacity comparison alone does not prove a student-seat shortage; enrolment/demand data must be connected to prove that.
- What-if results now show signatures that resolved, remain, or are new between the saved proposal and alternative. A recommendation is based on transparent item/severity comparisons and is labelled as a review recommendation, not a calibrated probability or an approval decision.
- Regression tests cover time parsing/overlap boundaries, impact comparison categories, and insufficient-data behaviour.

## Data source truthfulness

`college database evidence` means a result is tied to a stored record. `college database check` is a bounded comparison that did not prove a conflict. `insufficient data` means the current inputs or records do not support a reliable check. Rule-based impacts remain hypotheses. Synthetic demonstration records must never be represented as official ACE Engineering College records.

The official timetable API remains opt-in and requires an institution-approved HTTPS endpoint and token. Configure `COLLEGE_DATA_API_URL`, `COLLEGE_DATA_API_TOKEN`, and `COLLEGE_DATA_API_TIMEOUT` through the deployment environment/secret manager. Do not commit real tokens to `.env`, source control, or the ZIP release. Verify data ownership, field mapping, sync age, row reconciliation, and the official system's terms before enabling it. This repository does not include live institutional credentials.

## Local verification

Run from the project root in a clean Python environment:

```bash
python -m pip install -r requirements.txt
python -m compileall -q app migrations tests
python -m pytest -q
python scripts/preflight.py
python scripts/validate_migration_graph.py
python scripts/demo_impact_analysis.py path/to/authorized-real-input.json  # requires authorized real data; no bundled sample
```

For the supported local container workflow, also run:

```bash
docker compose -f docker-compose.local.yml config --quiet
```

A successful syntax check or standalone demo is not a substitute for the full pytest suite. PostgreSQL concurrency guards, SMTP delivery, backup restoration, HTTPS, browser tests and load tests must be run in a correctly configured staging environment. Never claim a 500-user load test or production deployment passed until the actual run output has been reviewed.

## Production readiness checklist

- [ ] Authorized official data source and data owner approved
- [ ] Real secrets stored in deployment secret manager; no secrets in repository/archive
- [ ] PostgreSQL provisioned; migrations applied and verified
- [ ] HTTPS and secure cookies configured; production preflight passes
- [ ] Real SMTP provider configured and delivery tested
- [ ] Role and ownership checks verified for scenarios, records and exports
- [ ] Backups and a restore drill verified
- [ ] Browser smoke, PostgreSQL concurrency, and load tests run in staging
- [ ] Data freshness and sync failure monitoring configured
- [ ] Impact explanations reviewed by domain owners; false-positive/false-negative feedback tracked

## Additive release-acceptance reporting

Run `python scripts/release_acceptance.py` to report which release gates can be checked from repository files and which remain dependent on external services or authorized institutional access. It does not send network traffic, expose secret values, or mark an external gate complete merely because an environment variable exists. It is intentionally non-destructive and does not remove or replace application modules.

The full application, PostgreSQL, SMTP, official ACEEC ERP/SIS, browser, load, restore, and stakeholder-validation gates must be run against their real test/staging dependencies. Keep the resulting logs/reports as release evidence.
