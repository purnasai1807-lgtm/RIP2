# THE RIPPLE — uploaded activity CSV integration

## What changed

- Uploading a full-schema `activities.csv` on **Activity Priority** still produces the scored CSV and now also attempts to activate the activity table in the campus dependency model.
- Activation is staged: the app copies the bundled supporting tables into a temporary directory, replaces `activities.csv`, and runs the dataset's cross-table validation. It only switches the active dataset after validation succeeds. Invalid uploads do not replace the current active dataset.
- `/dataset-analysis` and `/api/dataset-analysis` now analyze the active dataset, including the uploaded activities, for variants V1, V2 and V3.
- The dataset-analysis page indicates when the upload is active and provides a CSRF-protected reset to the bundled baseline.
- The dataset ZIP download follows the active dataset.
- Priority score and impact status remain distinct. A priority score is not a probability of disruption; impact flags come from the service, room and dependency data.

## How to use

1. Start the Flask app using the project's normal setup (`pip install -r requirements.txt`, configure `.env` as needed, then `flask --app run.py run` if using the project's run entry point).
2. Sign in and open **Activity Priority**.
3. Upload a UTF-8 `activities.csv` with all 28 activity-table columns. A small four-column CSV can be scored, but it cannot replace the activity table used for full ripple analysis.
4. Read the integration result. If cross-table validation fails, the CSV is scored but is not activated.
5. Open **Campus crisis dataset** and choose V1, V2 or V3. The report and JSON API use the active activities table.
6. Use **Reset to bundled baseline dataset** to discard the active upload.

## Phases represented in the application

1. **Run and baseline verification:** project requirements, existing tests and route checks.
2. **CSV ingestion and validation:** UTF-8 parsing, row limits, required columns, unique activity IDs, numeric weights, full-schema checks and cross-table references.
3. **Campus dependency model:** activities, rooms, services, service links, staff, equipment/work requests and activity dependencies remain connected through the 19-table model.
4. **Incident/direct impact:** V1/V2/V3 incident variants identify initial service failures and direct activity/service exposure.
5. **Ripple propagation:** cycle-safe service dependency closure and activity dependency analysis expose indirect impacts with causal paths.
6. **Recovery/decision support:** use existing constraint, cancellation-policy, repair-work and scenario/evidence features; recommendations must be treated as feasible only where hard constraints are explicitly checked. This prototype is decision support, not an operational safety certification or a live campus feed.
7. **Verification/reporting:** dataset validation, scenario summaries, JSON output, scored CSV download and active-dataset export.

## Important scope and accuracy notes

- Uploading one CSV updates only the activities table. The rooms, services, staff, dependency edges, repair data and incident definitions are retained from the bundled campus dataset. If those other tables change, they must be imported and validated too.
- Results are only as accurate as the uploaded records and supporting campus tables. Missing, stale or uncertain facts must not be presented as confirmed real-world conditions.
- The dependency analysis identifies dataset-backed exposure; it does not independently certify that a proposed room/time/staffing reassignment is safe or optimal.
- Full application integration tests require installing the dependencies in `requirements.txt` and running `pytest` in the target environment.
