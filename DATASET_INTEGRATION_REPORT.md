# THE RIPPLE Dataset Integration and Analysis Report

## Imported source
The exact user-supplied `The_Ripple_Dataset.zip` package is bundled under `data/ripple_dataset/`. The original CSV/JSON files and supporting documentation are preserved. The application reads them on demand; it does not insert synthetic teaching data into the institution's operational database.

## Coverage
- 19 CSV tables and `incident.json` are loaded by `app/dataset_engine.py`.
- 567 CSV records are loaded from the supplied CSVs.
- Buildings: 9; rooms: 26; activities: 35; approved activity modes: 45.
- Services: 38; room-to-service mappings: 106; service dependency links: 9.
- Activity dependencies: 34 (11 hard and 23 soft); constraints: 20.
- Staff directory: 62; baseline staff assignments: 43; staff roles: 14.
- Engineering personnel: 30; repair requests: 11; repair-map rows: 11; parts: 7.
- Room availability windows: 29; room-feature definitions: 29; facility contacts: 9.

## Validation
The extended validator checks duplicate/blank core identifiers and cross-table references for buildings, rooms, contacts, activities, activity modes, service links, room services, dependencies, room availability, staff assignments, engineering personnel, parts, work requests and repair maps. The supplied dataset passes these checks with zero reported errors and zero warnings.

## Analysis findings
The built-in incident variants produce these results from the supplied source data:
- V1 compound incident: 10 initially affected services; 16 services in dependency closure; 35/35 activities flagged as potentially disrupted; 19 rooms with service risks.
- V2 network backbone outage: 1 initial fault; 10 services in dependency closure; 35/35 activities flagged as potentially disrupted; 19 rooms with service risks.
- V3 power and canteen water faults: 4 initial faults; 4 services in dependency closure; 13/35 activities flagged as potentially disrupted; 7 rooms with service risks.

Service inventory at the dataset's initial state: 27 available, 2 degraded, and 9 unavailable. Activity priority counts: 6 critical, 14 high, 15 medium. Ten activities are explicitly cancellable; no critical/mandatory activity is marked cancellable. The report also surfaces all 20 constraint definitions and all 11 repair jobs, including prerequisites, required skill, required part, free-stock estimate, eligible-engineer count, and verification time.

## Application routes
- `/dataset-analysis` — authenticated HTML inventory and analysis dashboard, including variant selector.
- `/api/dataset-analysis?variant=V1` — authenticated JSON report; supports V1, V2, and V3.
- `/dataset-download.zip` — authenticated download of the exact bundled dataset files.

## Interpretation boundaries
These are dependency-based impact flags, not a certified recovery plan. A schedule solver must still validate every activity's time window, duration, room capacity/features/closures, service state, staff qualifications/availability/breaks, hard dependencies, and cancellation rules. A repair scheduler must validate skill coverage, non-preemptible job duration, staff concurrency, prerequisites, parts consumption, handover and verification. The supplied dataset is synthetic teaching data, not verified live ACE Engineering College data. No sensor/API integration or live automatic incident detection is claimed.

## Verification performed in this build
- Python syntax compilation for the engine and route module.
- Dataset validator and V1/V2/V3 engine checks.
- Focused pytest checks for dataset integrity, scenario variants, and report coverage.
- ZIP integrity and source dataset content checks.
- Full Flask/browser/PostgreSQL production integration remains environment-dependent and must be verified in the deployment environment.
