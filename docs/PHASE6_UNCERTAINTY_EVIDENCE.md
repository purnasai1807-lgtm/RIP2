# Phase 6 — Uncertainty and Evidence

## Scope
Phase 6 gives each decision scenario an evidence register. Every evidence item stores a label, source type, source reference, status, 0–100 confidence, observation timestamp, optional expiry timestamp, notes, creator, and created/updated timestamps. Status values are `Verified`, `Unverified`, `Disputed`, and `Stale`.

## Analysis behavior
- Evidence items are serialized into the reproducibility snapshot used by Phase 5.
- A record is treated as stronger evidence only when its status is `Verified`, confidence is at least 80%, and it is not stale/expired.
- A record with an expiry in the past is treated as stale. An observation older than 30 days without an expiry is treated as potentially stale.
- Unverified, disputed, stale, or low-confidence evidence produces an explicit uncertainty impact and a mitigation recommending source validation and a rerun.
- Every new/changed evidence record invalidates the prior reproducibility snapshot and returns the scenario to Draft until analysis is rerun.
- Evidence sensitivity compares the current status with a hypothetical status; it does not change the saved evidence or approve an operational decision.

## Endpoints
- `POST /scenarios/<id>/evidence` — add evidence.
- `POST /scenarios/<id>/evidence/<evidence_id>/update` — update status, confidence, reference, timestamps, and notes.
- `POST /scenarios/<id>/evidence/<evidence_id>/delete` — remove evidence.
- `POST /scenarios/<id>/sensitivity` — compare a hypothetical evidence status.
- `GET /scenarios/<id>/verify-analysis` — Phase 5 deterministic integrity check.

All scenario evidence endpoints require login and use the scenario ownership check. The same CSRF protection used by other form posts applies. Evidence is not a substitute for an authoritative live integration, calibrated probabilities, or a human review.

## Migration
Apply `flask --app wsgi:app db upgrade` to create `scenario_evidence` after revision `20261013_12`.
