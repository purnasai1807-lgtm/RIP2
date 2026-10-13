"""Read-only connectivity and reconciliation preview for the approved ACEEC API.

This script does not change the database or provider. It requires the official endpoint
and token supplied through the deployment secret store. Output contains counts and field
names only; it does not print tokens, full timetable rows, or personal data.
"""
from __future__ import annotations
import os
import sys
from collections import Counter
from app import create_app, db
from app.integrations.college_source import fetch_timetable, CollegeSourceError
from app.models import Department, Course, Room, TimetableEntry


def main() -> int:
    if not os.environ.get("COLLEGE_DATA_API_URL") or not os.environ.get("COLLEGE_DATA_API_TOKEN"):
        print("BLOCKED: configure the institution-approved HTTPS endpoint and token in the secret store.", file=sys.stderr)
        return 2
    app = create_app({"APP_ENV": "production", "SKIP_AUTO_SCHEMA": True})
    try:
        with app.app_context():
            rows = fetch_timetable(app)
            provider_ids = [r["record_id"] for r in rows if r.get("record_id")]
            duplicate_ids = [key for key, count in Counter(provider_ids).items() if count > 1]
            if duplicate_ids:
                raise CollegeSourceError("Provider payload has duplicate record IDs.")
            existing_ids = {x for (x,) in db.session.query(TimetableEntry.source_record_id).filter(
                TimetableEntry.source_system == "official_api", TimetableEntry.source_record_id.isnot(None)).all()}
            incoming_ids = set(provider_ids)
            matched = len(existing_ids & incoming_ids)
            new = len(incoming_ids - existing_ids)
            absent = len(existing_ids - incoming_ids)
            departments = {x.code for x in Department.query.all()}
            courses = {x.code for x in Course.query.all()}
            rooms = {x.code for x in Room.query.all()}
            missing_departments = sum(r["department_code"] not in departments for r in rows)
            missing_courses = sum(r["course_code"] not in courses for r in rows)
            missing_rooms = sum(r["room_code"] not in rooms for r in rows)
            print("Official API connection: PASS (HTTPS response authenticated and contract validated)")
            print(f"Provider rows validated: {len(rows)}")
            print(f"Rows with stable provider IDs: {len(provider_ids)}; existing ID matches: {matched}; new IDs: {new}; local IDs absent from source: {absent}")
            print(f"Local reference gaps (department/course/room): {missing_departments}/{missing_courses}/{missing_rooms}")
            print("DRY RUN ONLY: no database writes or deletions performed.")
            if missing_departments or missing_courses or missing_rooms:
                print("REVIEW REQUIRED: resolve reference gaps with the institutional data owner before sync.", file=sys.stderr)
                return 3
            print("Reconciliation preview passed. Review counts with the authorized data owner before running sync-official-timetable --confirm.")
            return 0
    except Exception as exc:
        print(f"Official integration check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
