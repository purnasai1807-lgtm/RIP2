# Phase 2 — Incident input and detection

Phase 2 adds an authenticated incident register to `ripple111`. It records a reported disruption and its operational updates; it does **not** claim that a report is independently verified or that downstream ripple analysis has run.

## Included

- Incident record: unique incident code, title, description/evidence note, category, severity, status, location, reporter, report timestamp, start timestamp, estimated duration, resolution timestamp, and last-updated timestamp.
- Optional links to a Phase 1 campus resource and activity, with existence validation.
- Incident lifecycle: `Reported`, `Investigating`, `Monitoring`, `Resolved`, `False alarm`.
- Severity: `Low`, `Medium`, `High`, `Critical`.
- Categories: `Power`, `Network`, `Water`, `Fire/Safety`, `Facilities`, `Transport`, `Staffing`, `Other`.
- Append-only update history for initial reports, status changes, ETA changes, notes, who made the change, and when.
- HTML register at `/incidents`, detail/history at `/incidents/<id>`, text search and status/severity filters.
- Session-authenticated JSON endpoints at `/api/incidents` and `/api/incidents/<id>`; JSON writes use `POST` and `PATCH` and require `X-CSRF-Token` from the authenticated session.
- Coordinators and administrators can create/update; signed-in users can read. All changes create audit events. CSRF validation applies to browser and API writes.
- Alembic migration `20261013_11_campus_incidents.py` adds both tables and indexes.

## Local setup

1. Install the packages from `requirements.txt` in the project's virtual environment.
2. Configure the local `DATABASE_URL` as documented in `docs/local-development.md`.
3. For local development, schema auto-creation includes the new tables. For production, deploy the code and run `flask --app wsgi:app db upgrade` against the configured PostgreSQL database before serving traffic.
4. Sign in as a coordinator/admin, open **Incidents**, and report a test incident using non-operational/demo information. Do not enter sensitive personal information.

## API examples

Every endpoint requires an authenticated session. Every write also requires the CSRF token associated with that session in `X-CSRF-Token`.

`GET /api/incidents?status=Investigating&severity=High` lists matching incidents.

`POST /api/incidents` JSON body:

```json
{
  "incident_code": "INC-NET-001",
  "title": "Library network outage",
  "description": "Network operations reported connectivity loss.",
  "incident_type": "Network",
  "severity": "High",
  "location": "Library",
  "estimated_duration_minutes": 45
}
```

`PATCH /api/incidents/1` JSON body:

```json
{
  "status": "Monitoring",
  "estimated_duration_minutes": 20,
  "note": "Connectivity has returned; monitoring for stability."
}
```

Omitted fields in a PATCH retain their current values. Send an empty `resource_id` or `activity_id` to unlink it. The status is not automatically set to resolved merely because the ETA passes; an authorized operator must update the status based on evidence.

## Detection boundary

This phase provides structured human-reported detection/intake and update APIs. Automatic sensor/SCADA/network-monitor integrations are not enabled because no authorized incident-source endpoint or credentials are configured. Integrating an actual source requires an institution-approved source contract, authentication, deduplication policy, freshness monitoring and failure handling. No fictional sensor readings or incidents are seeded.

## Verification status

Python syntax compilation is part of the build check. The full Flask/SQLAlchemy test suite and PostgreSQL migration were not run in the authoring environment because Flask and Flask-SQLAlchemy are not installed there and package installation could not reach the package index. Run `pytest -q` and `flask --app wsgi:app db upgrade` in the project's configured environment before treating the deployment as release-verified.
