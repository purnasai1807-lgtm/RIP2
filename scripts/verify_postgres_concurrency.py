"""Exercise the PostgreSQL timetable overlap trigger with genuinely concurrent writers.

Use only a disposable/staging database after applying all migrations. The script
creates and removes uniquely named test rows. It never prints the database URL.
"""
from __future__ import annotations

import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        print("ERROR: DATABASE_URL must target a disposable PostgreSQL database.", file=sys.stderr)
        return 2
    engine = create_engine(url, pool_pre_ping=True, pool_size=4, max_overflow=0)
    suffix = uuid.uuid4().hex[:10].upper()
    dept_id = course_ids = room_id = None
    barrier = threading.Barrier(2)
    try:
        with engine.begin() as conn:
            guards = set(conn.execute(text("""SELECT tgname FROM pg_trigger
                WHERE NOT tgisinternal AND tgname = 'campusripple_timetable_overlap_guard'""")).scalars())
            if guards != {"campusripple_timetable_overlap_guard"}:
                raise RuntimeError("Timetable overlap trigger is missing; apply migrations first.")
            dept_id = conn.execute(text("INSERT INTO department(code,name) VALUES (:c,:n) RETURNING id"),
                {"c": "T" + suffix, "n": "Concurrency Test " + suffix}).scalar_one()
            course_ids = []
            for index in (1, 2):
                course_ids.append(conn.execute(text("""INSERT INTO course
                    (code,name,department_id,academic_year,semester)
                    VALUES (:c,:n,:d,'2099-00','1') RETURNING id"""),
                    {"c": f"C{index}{suffix}", "n": f"Concurrency Course {index} {suffix}", "d": dept_id}).scalar_one())
            room_id = conn.execute(text("""INSERT INTO room
                (code,name,room_type,capacity,is_active) VALUES (:c,:n,'Classroom',30,true) RETURNING id"""),
                {"c": "R" + suffix, "n": "Concurrency Room " + suffix}).scalar_one()

        def insert(course_id: int, faculty: str) -> str:
            try:
                barrier.wait(timeout=10)
                with engine.begin() as conn:
                    conn.execute(text("""INSERT INTO timetable_entry
                        (course_id,room_id,faculty_name,day_of_week,start_time,end_time,subject,source_system)
                        VALUES (:course,:room,:faculty,'Monday','09:00','10:00',:subject,'integration_test')"""),
                        {"course": course_id, "room": room_id, "faculty": faculty,
                         "subject": "Concurrent Test " + suffix})
                return "accepted"
            except DBAPIError as exc:
                # The trigger reports a PostgreSQL exclusion-style conflict (23P01).
                code = getattr(getattr(exc, "orig", None), "sqlstate", None)
                if code == "23P01" or "Timetable conflict" in str(exc.orig):
                    return "rejected_conflict"
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda args: insert(*args), [
                (course_ids[0], "Concurrent Faculty A"),
                (course_ids[1], "Concurrent Faculty B"),
            ]))
        if sorted(results) != ["accepted", "rejected_conflict"]:
            raise RuntimeError(f"Expected one accepted write and one conflict; got {results!r}")
        print("PASS: concurrent timetable writes serialized; exactly one overlapping room booking was accepted.")
        return 0
    except Exception as exc:
        print(f"FAIL: PostgreSQL concurrency check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    finally:
        if course_ids and room_id:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM timetable_entry WHERE course_id IN (:a,:b)"),
                             {"a": course_ids[0], "b": course_ids[1]})
                conn.execute(text("DELETE FROM course WHERE id IN (:a,:b)"),
                             {"a": course_ids[0], "b": course_ids[1]})
                conn.execute(text("DELETE FROM room WHERE id=:id"), {"id": room_id})
                conn.execute(text("DELETE FROM department WHERE id=:id"), {"id": dept_id})
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
