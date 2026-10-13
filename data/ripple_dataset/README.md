# THE RIPPLE — Campus Crisis Recovery Dataset (v2.2-cancellation-policy-audited)

This package describes a synthetic campus-wide disruption and its operating constraints. It is intended for impact analysis, activity rescheduling, engineering work allocation, and scenario comparison. It does not prescribe a solution strategy.

## Student glossary

Read `ACRONYMS_AND_DATA_GLOSSARY.md` for full building names, service prefixes, staff/room codes, part IDs, and scheduling terminology.

## Important operating semantics
- Times are campus-local `HH:MM`; intervals are half-open: an activity ending at 11:00 does not conflict with another starting at 11:00.
- Multi-value fields use semicolons.
- Every building has explicit power, network, water, and AV service records; the laboratory also has an explicit controlled-access service. A missing record is not a healthy state; report missing data as unknown.
- Room-level service IDs are in `room_services.csv`. Activity requirements name service types; the selected room determines the location-specific service instance.
- Service states are `available`, `degraded`, or `unavailable`. The lab access controller and auditorium AV controller are explicit services. Degraded is not sufficient for normal operation unless an explicitly permitted activity mode removes the relevant requirement.
- Service repair occurs only after the mapped job and verification complete; a prerequisite service/job must be complete first.
- Hard activity dependencies constrain the timetable. Soft dependencies are preferences/risks and should contribute penalties, not automatically make a plan impossible.
- Activity start times must be within `earliest_start` and `latest_start`, which already encode the permitted window. `max_advance_minutes` and `max_delay_minutes` are explicit cross-checks against original start.
- Room availability includes normal opening hours and explicit closures. Include setup/teardown when checking room occupancy.
- Staff qualifications are semicolon-delimited tags. A staff member must cover the activity's required role and be available for the full activity; breaks must be respected.
- Laboratory activities require a qualified lab technician and controlled-access venue. Food service requires a food-service lead and approved food venue.
- Engineering work units are synthetic. `work_units / work_units_per_hour` is active work duration; verification is added afterward. Work is non-preemptible. Parts are consumed once per job.
- Activity modes are approved scenario choices, not assumptions to invent. The offline fallback modes only remove network requirements and carry a quality penalty.

## Package contents
See `dataset_manifest.json` for the file catalogue and row counts. `constraints.csv` defines the intended hard constraints and objective preferences.

## Expected analysis
Teams should identify direct and indirect impacts, explain the causal path, create a feasible revised activity timetable, allocate engineering jobs to qualified personnel, compare at least two strategies, and report any unsatisfied or uncertain conditions. A heuristic failure is not proof of infeasibility.

## Data integrity notice
This is a synthetic teaching dataset. IDs, roles, service links, and rules are authoritative within the scenario. Do not assume any missing information is available; flag it. This package contains input data and rules only; it does not contain completed schedules or organizer validation results.

## v2.2 cancellation policy
Cancellation is forbidden for all critical and mandatory activities. Only the 10 explicitly designated optional activities in `activities.csv` have `cancellation_allowed=true`. A positive cancellation penalty does not override `cancellation_allowed=false`; such activities must be scheduled in a feasible plan. Deferral permission is a separate policy and does not imply cancellation permission. The supplied scenario has verified all-activity reference schedules; do not infer that every possible incident variant has been proved feasible.
