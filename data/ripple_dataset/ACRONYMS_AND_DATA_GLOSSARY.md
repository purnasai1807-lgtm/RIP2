# THE RIPPLE v2.2 — Student Acronyms, Codes & Data Dictionary

This glossary explains the abbreviations, identifier prefixes, status values, and commonly shortened terms actually used in the student dataset. It does **not** contain organizer solutions or recommended schedules.

## 1. Building IDs (exact full names)

| Code | Full building name | Purpose |
|---|---|---|
| `CAB` | Central Academic Block | Main examination and teaching block |
| `ABA` | Academic Block A | Computer teaching and assessment |
| `ABB` | Academic Block B | Training and project review |
| `ABC` | Academic Block C | Student support and flexible seminar rooms |
| `LIB` | Central Library | Study, research and quiet rooms |
| `LAB` | Central Laboratory | Controlled access; specialist activities require lab technician |
| `AUD` | Auditorium | Large event venue; incident affects power |
| `CAN` | Canteen Complex | Food handling requires water and power |
| `ADM` | Administration Annex | Registration, records and a backup conference venue |

**Important:** `ABA`, `ABB`, and `ABC` mean Academic Block A, B, and C. `LAB` is the Central Laboratory, whereas `LIB` is the Central Library. `AUD` is the Auditorium, `CAN` the Canteen Complex, and `ADM` the Administration Annex.

## 2. Identifier prefixes and their meaning

| Pattern | Meaning | Where to look |
|---|---|---|
| `A01`, `A02`, … | Activity identifier (not Academic Block A) | `activities.csv` |
| `R01`, `R02`, … | Room identifier | `rooms.csv` |
| `J01`, `J02`, … | Engineering repair/work-request identifier | `work_requests.csv` |
| `E01`, `E02`, … | Engineering personnel identifier | `engineering_personnel.csv` |
| `P01`, `P02`, … | Event staff/personnel identifier | `staff_directory.csv` |
| `FC01`, `FC02`, … | Facility/site contact identifier | `facility_contacts.csv` |
| `SA001`, … | Baseline staff-assignment identifier | `staff_assignments.csv` |
| `RA-R01-1`, … | Room availability record identifier | `room_availability.csv` |
| `D01`, `D02`, … | Activity dependency record identifier | `dependencies.csv` |
| `C01`, `C02`, … | Constraint/rule identifier | `constraints.csv` |
| `INC-01` | Incident identifier | `incident.json` |
| `V1`, `V2`, `V3` | Scenario variant identifiers; V1 is the default | `incident.json` |
| `A01-M1`, `A01-M2`, … | Activity-mode identifier; suffix M1/M2 identifies a mode, not a room | `activity_modes.csv` |

## 3. Service abbreviations and composite IDs

| Code | Full form / meaning | Example |
|---|---|---|
| `PWR` | Power/electrical supply | `PWR-CAB`: power service in Central Academic Block |
| `NET` | Data network / connectivity | `NET-LIB`: network service in Central Library |
| `WAT` | Water supply | `WAT-CAN`: water service in Canteen Complex |
| `AV` | Audio-visual equipment/service | `AV-AUD`: audio-visual service in Auditorium |
| `ACCESS` | Controlled building/room access service | `ACCESS-LAB`: access control for Central Laboratory |
| `CORE` | Campus network backbone (not a building code) | `NET-CORE`: campus-wide core network service |

For ordinary location-based service IDs, the code before the hyphen identifies the service type and the code after the hyphen identifies the building. Service states and dependencies are defined in `services.csv` and `service_links.csv`; do not infer that a service is available just because a matching service ID exists.

## 4. Facility, room and staffing terminology

| Term | Meaning |
|---|---|
| `facility_incharge_id` | Identifier of the person responsible for the room/facility; use the corresponding contact/person records where provided |
| `site_contact_id` | Facility contact for a building (`FC..`) |
| `room_id` / `building_id` | Foreign keys joining a room to a building |
| `required_features` | Features a room must possess for an activity or mode |
| `required_service_types` | Services needed for an activity; resolve these to the selected room’s service IDs through `room_services.csv` |
| `required_staff_role` | Role or qualification needed to supervise/run an activity |
| `required_technical_support_count` | Number of separately qualified technical support staff needed |
| `eligible_staff` | Permitted engineering personnel IDs for a repair job, separated by semicolons |
| `secondary_skills` | Additional engineering skills the worker may use |
| `work_units_per_hour` | Synthetic engineering throughput used to calculate repair duration; not a monetary rate |
| `work_units` | Amount of synthetic repair effort required by a job |
| `handover` | Post-work handover time before a repair is considered restored |
| `verification` | Post-work confirmation time before a service becomes usable |
| `preemptible` | Whether a repair can be interrupted and resumed |
| `max_parallel_engineers` | Maximum simultaneous engineers allowed on a job |
| `maximum_parallel_jobs` | Maximum simultaneous jobs allowed for an engineer |
| `AV` in room features | Audio-visual capability, not an independent guarantee of a healthy AV service |

## 5. Activity and scheduling terms

| Field / term | Meaning |
|---|---|
| `original_start`, `original_end`, `original_room_id` | Published baseline timetable, before changes |
| `earliest_start`, `latest_start` | Permitted activity or repair start-time bounds, depending on the table |
| `duration_minutes` | Standard activity duration (or selected activity-mode duration) |
| `minimum_duration_minutes` | Lower bound on activity duration |
| `max_delay_minutes`, `max_advance_minutes` | Limits on how far the activity can move later or earlier |
| `relocatable` | Whether an activity may move to a different valid room |
| `cancellation_allowed` | Whether the solver is allowed to cancel the activity; **true does not mean already cancelled** |
| `cancellation_penalty` | Cost/score penalty when an allowed cancellation is chosen |
| `deferral_allowed` | Whether deferral is permitted by the rules |
| `remote_mode_allowed` | Whether a remote format is permitted; still respect declared modes and services |
| `setup_minutes`, `teardown_minutes` | Extra room occupancy before/after an activity |
| `priority_weight` | Relative optimization weight for the activity |
| `hard` dependency | Must be satisfied for a feasible timetable |
| `soft` dependency | Preference/risk represented by a penalty; not an automatic blocker |
| `minimum_gap_minutes` | Required or preferred separation between dependent activities, according to constraint type |
| `quality_penalty` | Cost for using an alternative approved activity mode |
| `baseline` | Original assignment or plan, not the proposed final schedule |
| `half-open interval` | A booking `[start, end)` includes its start but not its end |

## 6. Repair parts: identifiers explained

| Part ID | Meaning |
|---|---|
| `FUSE` | Electrical protective fuse |
| `BREAKER` | Electrical circuit breaker |
| `NETWORK_MODULE` | Replacement network hardware module |
| `PATCH_CORD` | Network patch cable/cord |
| `VALVE_KIT` | Water-valve repair kit |
| `ACCESS_SENSOR` | Controlled-access sensor |
| `AV_CONTROLLER` | Audio-visual controller |

`quantity_available` is the declared stock quantity, `reserved_quantity` is already reserved stock, and `compatible_job_ids` identifies repairs that can use the part. The unit `each` means individual items.

## 7. Staff role tags (exact identifiers)

| Role tag | Full meaning / description |
|---|---|
| `assessment_officer` | Assessment Officer |
| `counsellor` | Counsellor |
| `event_producer` | Event Producer |
| `event_support` | Event Support |
| `faculty_exam` | Faculty Exam |
| `faculty_presenter` | Faculty Presenter |
| `faculty_reviewer` | Faculty Reviewer |
| `food_service_lead` | Food Service Lead |
| `lab_technician` | Lab Technician |
| `library_support` | Library Support |
| `records_officer` | Records Officer |
| `student_support` | Student Support |
| `technical_facilitator` | Technical Facilitator |
| `technical_support` | Technical Support |

Role and qualification tags are exact data values: do not assume that a similarly named role can substitute unless the dataset permits it.

## 8. Room feature tags (exact identifiers)

| Feature tag | Meaning | Safety-marked in dataset? |
|---|---|---|
| `accessible` | Accessible | true |
| `assessment` | Assessment | false |
| `auditorium` | Auditorium | false |
| `av` | Audio-visual equipment/capability | false |
| `collaboration` | Collaboration | false |
| `computers` | Computers | false |
| `conference` | Conference | false |
| `controlled_access` | Controlled Access | true |
| `counselling` | Counselling | false |
| `exam_seating` | Exam Seating | false |
| `food_service` | Food Service | true |
| `lab_benches` | Lab Benches | true |
| `lecture` | Lecture | false |
| `meeting` | Meeting | false |
| `network` | Network | false |
| `power` | Power | false |
| `private` | Private | false |
| `projector` | Projector | false |
| `quiet` | Quiet | false |
| `records` | Records | false |
| `review` | Review | false |
| `seating` | Seating | false |
| `serving` | Serving | false |
| `showcase` | Showcase | false |
| `specialist_lab` | Specialist Lab | false |
| `stage` | Stage | false |
| `study` | Study | false |
| `training` | Training | false |
| `workstations` | Workstations | false |

Safety-marked features must not be silently waived. A room feature is a capability; service availability is checked separately.

## 9. File format and status values

- **CSV** = Comma-Separated Values. The 19 CSV files are linked by identifier fields.
- **JSON** = JavaScript Object Notation. `incident.json` contains incident details and scenario variants.
- **README** = Read Me: a plain-language guide to the package.
- **ID** = Identifier. The ID string is a key, not a numeric quantity.
- **HH:MM** = 24-hour hours:minutes, campus-local time (for example `13:30` = 1:30 PM).
- **`true` / `false`** = Boolean yes/no; these values are not cancellation outcomes.
- **`;`** = Semicolon used inside one CSV cell to separate multiple IDs, tags, or values.
- **`available`** = Usable state when all applicable dependencies and constraints are met.
- **`unavailable`** = Not usable.
- **`degraded`** = Reduced operation; not normal-operation ready unless an approved mode explicitly permits it.
- **`unknown`** = Missing or unverified state; do not treat it as available.
- **`open`** in `work_requests.csv` = Repair request not yet completed, not a claim that the affected service is operational.
- **`none`** = No declared closure window or other value in that field, as appropriate.
- **`event_day`** = The simulated campus event day.

## 10. How to resolve a code you encounter

1. Find its prefix or exact value in this glossary.
2. Open the table named in the corresponding section and match its full ID.
3. Follow foreign keys to other tables (for example: activity → room → building → room services → service state).
4. For room suitability, check capacity, features, availability, staffing, and actual service state over the full activity interval.
5. If a code or state is absent or ambiguous, flag it as unknown rather than guessing.

**This document is explanatory only.** The authoritative feasibility rules are in `optimization_rules.md`, `constraints.csv`, and the corresponding source tables.
