# Phase 7 — Mitigation and Recovery Tracking

Phase 7 converts impact hypotheses into owned tasks without executing operational changes automatically.

## Features
- Create mitigation tasks per decision, optionally linked to an impact.
- Assign a responsible owner, priority, due date, description and success criteria.
- Track Open, In Progress, Blocked, Completed and Cancelled states.
- Record progress/completion evidence and append audit events.
- Enforce owner-scoped scenario access for both create and update operations.
- Migration `20261013_14_phase7_mitigation_actions.py` creates the task table and indexes.

## Run
Apply migrations with `flask --app wsgi:app db upgrade`, then open a decision page and use **Phase 7 · Mitigation & Recovery**.

Tasks are planning records only. They do not directly change official timetables, notify third parties, or assert that a real-world recovery has occurred. Verify outcomes with responsible campus staff.
