"""Serialize and reject overlapping timetable and exam writes in PostgreSQL.

Revision ID: 20261011_02
Revises: 20261011_01
"""
from alembic import op
revision = '20261011_02'
down_revision = '20261011_01'
branch_labels = None
depends_on = None

TIMETABLE_TRIGGER = r'''
CREATE OR REPLACE FUNCTION campusripple_check_timetable_overlap() RETURNS trigger AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('campusripple:timetable:' || NEW.day_of_week));
  IF EXISTS (
    SELECT 1 FROM timetable_entry t
    WHERE t.id IS DISTINCT FROM NEW.id
      AND t.day_of_week = NEW.day_of_week
      AND t.start_time < NEW.end_time AND t.end_time > NEW.start_time
      AND (t.room_id = NEW.room_id OR lower(t.faculty_name) = lower(NEW.faculty_name) OR t.course_id = NEW.course_id)
  ) THEN
    RAISE EXCEPTION 'Timetable conflict: room, faculty, or course overlaps an existing entry'
      USING ERRCODE = '23P01';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS campusripple_timetable_overlap_guard ON timetable_entry;
CREATE TRIGGER campusripple_timetable_overlap_guard
BEFORE INSERT OR UPDATE ON timetable_entry
FOR EACH ROW EXECUTE FUNCTION campusripple_check_timetable_overlap();
'''
EXAM_TRIGGER = r'''
CREATE OR REPLACE FUNCTION campusripple_check_exam_overlap() RETURNS trigger AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('campusripple:exam:' || NEW.exam_date));
  IF EXISTS (
    SELECT 1 FROM exam_schedule e
    WHERE e.id IS DISTINCT FROM NEW.id
      AND e.exam_date = NEW.exam_date
      AND e.start_time < NEW.end_time AND e.end_time > NEW.start_time
      AND (e.room_id = NEW.room_id OR e.course_id = NEW.course_id)
  ) THEN
    RAISE EXCEPTION 'Exam conflict: room or course overlaps an existing exam'
      USING ERRCODE = '23P01';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS campusripple_exam_overlap_guard ON exam_schedule;
CREATE TRIGGER campusripple_exam_overlap_guard
BEFORE INSERT OR UPDATE ON exam_schedule
FOR EACH ROW EXECUTE FUNCTION campusripple_check_exam_overlap();
'''

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        from sqlalchemy import text
        timetable_conflicts = bind.execute(text("""
            SELECT count(*) FROM timetable_entry a JOIN timetable_entry b ON a.id < b.id
            AND a.day_of_week = b.day_of_week AND a.start_time < b.end_time AND a.end_time > b.start_time
            AND (a.room_id = b.room_id OR lower(a.faculty_name) = lower(b.faculty_name) OR a.course_id = b.course_id)
        """)).scalar_one()
        exam_conflicts = bind.execute(text("""
            SELECT count(*) FROM exam_schedule a JOIN exam_schedule b ON a.id < b.id
            AND a.exam_date = b.exam_date AND a.start_time < b.end_time AND a.end_time > b.start_time
            AND (a.room_id = b.room_id OR a.course_id = b.course_id)
        """)).scalar_one()
        if timetable_conflicts or exam_conflicts:
            raise RuntimeError(f'Cannot install conflict guards: {timetable_conflicts} timetable and {exam_conflicts} exam conflict pairs exist. Resolve them, back up, and retry.')
        op.execute("""CREATE OR REPLACE FUNCTION campusripple_check_timetable_overlap() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtext('campusripple:timetable:' || NEW.day_of_week));
          IF EXISTS (SELECT 1 FROM timetable_entry t WHERE t.id IS DISTINCT FROM NEW.id
            AND t.day_of_week = NEW.day_of_week AND t.start_time < NEW.end_time AND t.end_time > NEW.start_time
            AND (t.room_id = NEW.room_id OR lower(t.faculty_name) = lower(NEW.faculty_name) OR t.course_id = NEW.course_id)) THEN
            RAISE EXCEPTION 'Timetable conflict: room, faculty, or course overlaps an existing entry' USING ERRCODE = '23P01';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
        op.execute('DROP TRIGGER IF EXISTS campusripple_timetable_overlap_guard ON timetable_entry')
        op.execute("CREATE TRIGGER campusripple_timetable_overlap_guard BEFORE INSERT OR UPDATE ON timetable_entry FOR EACH ROW EXECUTE FUNCTION campusripple_check_timetable_overlap()")
        op.execute("""CREATE OR REPLACE FUNCTION campusripple_check_exam_overlap() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtext('campusripple:exam:' || NEW.exam_date));
          IF EXISTS (SELECT 1 FROM exam_schedule e WHERE e.id IS DISTINCT FROM NEW.id
            AND e.exam_date = NEW.exam_date AND e.start_time < NEW.end_time AND e.end_time > NEW.start_time
            AND (e.room_id = NEW.room_id OR e.course_id = NEW.course_id)) THEN
            RAISE EXCEPTION 'Exam conflict: room or course overlaps an existing exam' USING ERRCODE = '23P01';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
        op.execute('DROP TRIGGER IF EXISTS campusripple_exam_overlap_guard ON exam_schedule')
        op.execute("CREATE TRIGGER campusripple_exam_overlap_guard BEFORE INSERT OR UPDATE ON exam_schedule FOR EACH ROW EXECUTE FUNCTION campusripple_check_exam_overlap()")

def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP TRIGGER IF EXISTS campusripple_timetable_overlap_guard ON timetable_entry')
        op.execute('DROP FUNCTION IF EXISTS campusripple_check_timetable_overlap()')
        op.execute('DROP TRIGGER IF EXISTS campusripple_exam_overlap_guard ON exam_schedule')
        op.execute('DROP FUNCTION IF EXISTS campusripple_check_exam_overlap()')
