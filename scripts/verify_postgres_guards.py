"""PostgreSQL-only integration smoke test for migration-installed overlap triggers."""
import os
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

url = os.environ.get('DATABASE_URL', '')
if not url.startswith(('postgresql://', 'postgresql+psycopg://', 'postgres://')):
    raise SystemExit('Set DATABASE_URL to a disposable PostgreSQL test database.')
if url.startswith('postgres://'):
    url = 'postgresql+psycopg://' + url[len('postgres://'):]
elif url.startswith('postgresql://'):
    url = 'postgresql+psycopg://' + url[len('postgresql://'):]
engine = create_engine(url, pool_pre_ping=True)
suffix = uuid.uuid4().hex[:10].upper()
with engine.begin() as conn:
    trigger_names = set(conn.execute(text("""SELECT tgname FROM pg_trigger WHERE NOT tgisinternal
        AND tgname IN ('campusripple_timetable_overlap_guard','campusripple_exam_overlap_guard')""")).scalars())
    if trigger_names != {'campusripple_timetable_overlap_guard', 'campusripple_exam_overlap_guard'}:
        raise SystemExit(f'Expected both PostgreSQL guards, found: {sorted(trigger_names)}. Apply migrations first.')
    dept = conn.execute(text("INSERT INTO department(code,name) VALUES (:code,:name) RETURNING id"),
                        {'code': 'T'+suffix, 'name': 'Integration Test '+suffix}).scalar_one()
    course1 = conn.execute(text("INSERT INTO course(code,name,department_id,academic_year,semester) VALUES (:c,:n,:d,'2099-00','1') RETURNING id"),
                           {'c':'C1'+suffix, 'n':'Integration Course 1 '+suffix, 'd':dept}).scalar_one()
    course2 = conn.execute(text("INSERT INTO course(code,name,department_id,academic_year,semester) VALUES (:c,:n,:d,'2099-00','1') RETURNING id"),
                           {'c':'C2'+suffix, 'n':'Integration Course 2 '+suffix, 'd':dept}).scalar_one()
    room = conn.execute(text("INSERT INTO room(code,name,room_type,capacity,is_active) VALUES (:c,:n,'Lab',30,true) RETURNING id"),
                        {'c':'R'+suffix, 'n':'Integration Room '+suffix}).scalar_one()
    user = conn.execute(text("INSERT INTO \"user\"(email,name,password_hash,role) VALUES (:e,:n,'test-only-hash','admin') RETURNING id"),
                        {'e':'integration-'+suffix.lower()+'@example.invalid', 'n':'Integration Test '+suffix}).scalar_one()
    conn.execute(text("INSERT INTO timetable_entry(course_id,room_id,faculty_name,day_of_week,start_time,end_time,subject,source_system) VALUES (:c,:r,'Integration Faculty','Monday','09:00','10:00','Integration Test','manual')"), {'c':course1,'r':room})
    failed_as_expected = False
    try:
        with conn.begin_nested():
            conn.execute(text("INSERT INTO timetable_entry(course_id,room_id,faculty_name,day_of_week,start_time,end_time,subject,source_system) VALUES (:c,:r,'Other Faculty','Monday','09:30','10:30','Expected Conflict','manual')"), {'c':course2,'r':room})
    except DBAPIError:
        failed_as_expected = True
    if not failed_as_expected:
        raise SystemExit('Timetable overlap trigger did not reject the expected room conflict.')
    exam_date = '2099-12-31'
    conn.execute(text("INSERT INTO exam_schedule(title,course_id,exam_date,start_time,end_time,room_id,status,created_by) VALUES ('Integration Exam 1',:c,:d,'09:00','10:00',:r,'Scheduled',:u)"), {'c':course1,'d':exam_date,'r':room,'u':user})
    exam_failed_as_expected = False
    try:
        with conn.begin_nested():
            conn.execute(text("INSERT INTO exam_schedule(title,course_id,exam_date,start_time,end_time,room_id,status,created_by) VALUES ('Expected Exam Conflict',:c,:d,'09:30','10:30',:r,'Scheduled',:u)"), {'c':course2,'d':exam_date,'r':room,'u':user})
    except DBAPIError:
        exam_failed_as_expected = True
    if not exam_failed_as_expected:
        raise SystemExit('Exam overlap trigger did not reject the expected room conflict.')
    conn.execute(text("DELETE FROM exam_schedule WHERE created_by=:u"), {'u':user})
    conn.execute(text("DELETE FROM timetable_entry WHERE course_id IN (:c1,:c2)"), {'c1':course1,'c2':course2})
    conn.execute(text("DELETE FROM room WHERE id=:id"), {'id':room})
    conn.execute(text("DELETE FROM course WHERE id IN (:c1,:c2)"), {'c1':course1,'c2':course2})
    conn.execute(text("DELETE FROM department WHERE id=:id"), {'id':dept})
    conn.execute(text("DELETE FROM \"user\" WHERE id=:id"), {'id':user})
print('PostgreSQL timetable and exam overlap guard integration checks passed.')
