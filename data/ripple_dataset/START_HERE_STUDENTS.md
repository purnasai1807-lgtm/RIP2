# THE RIPPLE: CAMPUS IN CRISIS — Student Data Pack (v2.2)

## Your mission
A compound infrastructure incident affects campus activities. Analyze direct and cascading impacts, build a feasible revised activity timetable, allocate qualified engineering staff to repairs, and compare at least two approaches. You may use software and AI tools. Your work must demonstrate the validity of the resulting plan, not merely display a proposed schedule.

## Start here
1. Read `README.md`, `ACRONYMS_AND_DATA_GLOSSARY.md`, `incident.json`, and `optimization_rules.md`.
2. Inspect `dataset_manifest.json` to understand the CSV tables.
3. Use `activities.csv` for the original activity timetable, requirements, time windows, and cancellation policy.
4. Use the room, service, staff, dependency, and repair tables to establish feasibility.
5. Produce your revised timetable, repair assignments, impact explanation, and strategy comparison.

## Important
- `cancellation_allowed=false` means the activity must be delivered in a valid complete plan; a cancellation penalty does not grant permission to cancel.
- `cancellation_allowed=true` only permits cancellation with the specified penalty; it does not mean the activity has been cancelled.
- A room matching capacity and features may still be unusable because of time, staff, or service constraints.
- Do not assume missing service data means a service is working.
- Do not weaken hard safety, qualification, room, or timing constraints to force a solution.
- Scenario variants V2 and V3 are optional stress tests, not a guarantee of feasibility.

## Files
The ZIP contains 19 linked CSV tables, the incident specification, rules, manifest, README, and this getting-started guide. No solution schedules or organizer audit files are included.
