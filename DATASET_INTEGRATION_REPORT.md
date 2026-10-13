# Dataset Integration Report

## What was added
- Bundled the exact supplied synthetic dataset package under `data/ripple_dataset/`.
- Added `app/dataset_engine.py` to load all 19 CSV tables plus `incident.json`.
- Added integrity checks for duplicate/blank primary IDs and core references across service links, room-service links, activity dependencies, activity room assignments, repair maps, and work-request prerequisites.
- Added service dependency traversal with causal paths, activity risk flags, and forward propagation over hard activity dependencies.
- Added authenticated HTML page `/dataset-analysis` and authenticated JSON endpoint `/api/dataset-analysis?variant=V1`.
- Added V1, V2, V3 variant selection and acceptance tests in `tests/test_dataset_engine.py`.

## Dataset verification performed
- All 19 CSV tables were read successfully.
- Core dataset integrity validator returned valid with zero errors.
- Observed counts include 35 activities, 38 services, 26 rooms, 34 activity dependency edges, 106 room-service mappings, and 11 work requests.
- Direct engine checks returned:
  - V1: 10 initially affected services; 16 services in dependency closure.
  - V2: 1 initially affected service; 10 services in dependency closure.
  - V3: 4 initially affected services; 4 services in dependency closure.
- Python syntax compilation passed for the new engine, modified routes module, and new test module.

## Not yet verified
- Full Flask application startup and browser end-to-end tests were not run in this execution environment because Flask and the project's dependencies are not installed here.
- Pytest was not run as a full suite.
- This integration flags impacts; it does not yet solve/certify the revised timetable or engineering repair schedule. It must not be described as a fully optimized or certified plan.
- Dataset is synthetic teaching data, not verified live ACE Engineering College data.

## Run locally
1. Extract this ZIP.
2. In the project folder, create/activate your Python virtual environment.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set a strong local `SECRET_KEY`; never commit `.env`.
5. Start using the project's existing README instructions.
6. Sign in, open **Ripple dataset**, and choose V1/V2/V3.
7. Run tests with `pytest -q`.
