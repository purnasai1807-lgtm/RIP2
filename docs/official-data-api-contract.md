# CampusRipple official timetable API contract

This is a connector contract, not a claim that ACE Engineering College currently exposes this endpoint. The institution's IT/data owner must approve the endpoint, field mapping, retention policy, and service account before configuration.

## Request

- Method: `GET`
- URL: `COLLEGE_DATA_API_URL` (HTTPS is mandatory)
- Authentication: `Authorization: Bearer <COLLEGE_DATA_API_TOKEN>`
- Accept: `application/json`
- Maximum response: 5 MiB; maximum rows: 5,000; timeout is configurable (default 15 seconds).
- API token is stored only in the deployment secret manager/environment. Never put it in a browser, repository, CSV, or issue tracker.

## Response example

```json
{
  "timetable": [
    {
      "record_id": "source-schedule-id-001",
      "department_code": "CSD",
      "department_name": "Computer Science and Design",
      "course_code": "CSD-101",
      "course_name": "Introduction to Computing",
      "academic_year": "2026-27",
      "semester": "1",
      "room_code": "LAB-01",
      "room_name": "Programming Laboratory",
      "room_type": "Lab",
      "capacity": 40,
      "faculty_name": "Faculty Name",
      "day_of_week": "Monday",
      "start_time": "10:00",
      "end_time": "11:00",
      "subject": "Programming"
    }
  ]
}
```

Required fields: `department_code`, `department_name`, `course_code`, `course_name`, `academic_year`, `semester`, `room_code`, `room_name`, `faculty_name`, `day_of_week`, `start_time`, `end_time`, and `subject`. `record_id`, `room_type`, and `capacity` are optional. Times use 24-hour `HH:MM`; end time must be later than start time. Capacity must be an integer from 0 through 10,000.

## Safety and reconciliation

- The connector is read-only toward the source system.
- Invalid rows, room/faculty overlaps, or a failed batch roll back local timetable changes.
- Imported rows are marked `source_system=official_api`, and `source_synced_at` records the most recent sync time.
- Existing records are not automatically deleted when absent from a later response; removal requires a reviewed reconciliation workflow.
- Confirm source timezone, academic-year semantics, cancellation states, and stable `record_id` behavior before production use.
- Use a staging endpoint and synthetic/test data first. Verify record counts and a sample against an official export before enabling production sync.


## Application API (session-authenticated)

The browser application also exposes the following authenticated v1 endpoints. They use the same login session and return `Cache-Control: no-store`; they are not a public bearer-token API.

- `GET /api/v1/meta` — supported decision domains, change variables and analysis version.
- `POST /api/v1/analyze` — run a non-persistent proposed-change analysis.
- `POST /api/v1/compare` — compare proposed and alternative values without changing saved scenarios.
- `GET /api/v1/scenarios?page=1&per_page=20&q=...` — list only the authenticated user's scenarios, with bounded pagination (maximum 100 items per page).
- `GET /api/v1/scenarios/<id>` — return one scenario and its impact chain; owners can view their own scenarios, while coordinators/admins may view workspace scenarios. Other users receive 404.

JSON POST requests still require the session-bound CSRF token in `X-CSRF-Token`; the analysis and comparison endpoints do not mutate saved scenarios. API payloads deliberately omit passwords, reset tokens, verification tokens, and other account secrets. Before external integration, add a separately reviewed client-authentication and rate-limiting strategy rather than treating browser-session auth as a general API credential.
