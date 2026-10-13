# Phase 5 — Decision intelligence and reproducible analysis

## Implemented

- Transparent rule-based hypotheses remain distinct from record-backed evidence; each impact retains source label and optional source record reference.
- Each run persists the rule version, UTC generation time, canonical input/evidence snapshot, SHA-256 input fingerprint, and SHA-256 result fingerprint.
- `GET /scenarios/<id>/verify-analysis` (authenticated and scenario-authorized) validates the stored input snapshot, persisted result, and deterministic replay against the exact evidence snapshot used at analysis time. It returns explicit checks and fingerprints; legacy analyses return HTTP 409 and must be re-run to create a snapshot.
- Scenario JSON exports include the analysis version and reproducibility fingerprints.
- Authorized reviewers can record Confirmed, Incorrect, or Uncertain feedback with an observed outcome. A reviewer may update their own feedback; the record is tied to the analysis rule version.
- Admin quality page reports counts as human feedback, not model accuracy. Admin-only CSV export supports offline analysis by rule version, source, level, severity, evidence reference, and reviewer outcome.
- Scenario approval remains a separate human workflow. Analysis/simulation does not mutate official timetable or campus records.

## API verification example

`GET /scenarios/123/verify-analysis`

A successful response includes `verified: true` and three checks: `input_snapshot_integrity`, `stored_result_integrity`, and `deterministic_replay_match`. A mismatch should trigger re-analysis and human review before the report is relied upon.

## Offline evaluation protocol

1. Export the labeled feedback CSV from the admin quality page.
2. Have an authorized reviewer adjudicate outcomes against source records; do not assume feedback alone is ground truth.
3. Split labeled cases by scenario/time into development and held-out evaluation sets to avoid leakage.
4. Report precision/recall only for a clearly defined binary label and only on independently adjudicated cases; report class counts and uncertainty. Do not claim calibration without probability outputs and an appropriate calibration study.
5. Compare versions and retain the export, label policy, split policy, and evaluation script as audit artifacts.

## Migration and verification

- Migration `20261013_12_analysis_reproducibility.py` adds nullable snapshot/fingerprint fields so existing records remain readable; legacy records can be re-analyzed to gain fingerprints.
- Run `flask --app wsgi:app db upgrade`, then `python -m pytest -q` in the configured environment.
- Full live database, browser, and production verification still requires the deployment dependencies and authorized environment. No predictive accuracy claim is made by this implementation.
