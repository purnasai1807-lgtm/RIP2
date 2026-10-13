# Phase 4 — Multi-level ripple tracing and response support

## Included

- Authenticated incident HTML report at `/incidents/<id>/ripple-analysis`.
- Authenticated JSON report at `/api/incidents/<id>/ripple-analysis`; optional `?depth=1..8` bounds graph traversal.
- Breadth-first traversal from the incident-linked resource and/or activity through explicit `ActivityDependency` records.
- Multi-level path explanations, stable source references, duplicate-node consolidation, severity prioritization, mitigation prompts, and explicit data limitations.
- Resource constraints attached to the starting resource are included for human feasibility review.
- Incident detail links to both Phase 3 direct-impact and Phase 4 ripple analysis.
- No automatic cancellations, status changes, notifications, or approvals are made by analysis.

## How to use

1. Sign in and create or open an incident.
2. Link it to a campus resource and/or activity. The trace needs an explicit starting point.
3. Maintain dependency records in the campus data model. A dependency means the source activity requires the target resource/activity.
4. Select **Run ripple analysis**. Review each level, causal path, source reference, and suggested verification step.
5. Confirm effects with the accountable service/activity owner before making operational changes.

## Interpretation

Level 0 is the incident-linked starting resource/activity. Level 1 includes activities dependent on the linked resource/activity. Higher levels trace activities that depend on already exposed activities. Severity is a transparent prioritization heuristic, not a measured probability. Missing or incomplete dependency records can cause missed impacts. The graph is capped at eight levels to protect response time and avoid unbounded traversal.

## Verification status

The ripple engine's source compiles and its template parses; a dependency-light graph smoke test traversed a resource → activity → dependent activity chain. Full Flask integration tests, migrations, PostgreSQL concurrency, SMTP and browser end-to-end tests require the project dependencies and a configured environment. They could not be run in the constrained authoring environment because packages could not be downloaded.
