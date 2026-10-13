# Phase 3 — Direct Impact Analysis

## What it does

Phase 3 adds an authenticated, incident-centered direct impact view and JSON endpoint. It uses the Phase 1 campus graph and Phase 2 incident links to identify:

- the resource directly linked to the incident;
- activities whose dependency records point to that resource;
- hard/soft constraints attached to the linked resource, marked for owner verification;
- the activity directly linked to an incident; and
- activities that directly depend on that activity.

Each row carries a stable source reference, relationship explanation, prioritization severity, and a suggested verification action. Duplicate activity impacts are consolidated. Results include analysis timestamp, a one-hop method description, and explicit data-quality limitations.

## Routes

- HTML: `GET /incidents/<incident_id>/direct-impacts`
- JSON: `GET /api/incidents/<incident_id>/direct-impacts`

Both require authentication. The JSON response contains `analysis_type: direct-only`, `incident`, `analyzed_at`, `impact_count`, `impacts`, `source_refs`, `limitations`, and `method`.

## Method and safety boundaries

- Traversal is limited to one dependency edge from incident-linked records. This phase does **not** trace indirect ripple effects.
- It does not automatically change activity/resource statuses, cancel activities, notify people, or claim an activity has stopped.
- Constraint records are surfaced as items to assess; the engine does not claim a constraint has been violated without operational measurements.
- Severity is a deterministic prioritization heuristic based on incident severity, dependency importance, and activity criticality. It is not a probability or an official risk score.
- A missing incident link or missing dependency records is shown as a limitation, not interpreted as “no impact.”
- Only current records in the campus model are used. Incomplete or stale source data can cause omissions.

## Verification

`python -m compileall -q app tests/test_direct_impact.py` passed. A dependency-light smoke test of the direct impact engine passed for a linked resource, a dependent activity, and a resource constraint. The full Flask test suite could not be run in the current build environment because Flask is not installed there; run `pip install -r requirements.txt` in the project environment, then `pytest -q`.
