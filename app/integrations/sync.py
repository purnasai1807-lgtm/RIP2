"""Transactional synchronization from an institution-approved read-only source."""
from datetime import datetime, timezone
from sqlalchemy import or_
from app import db
from app.models import Department, Course, Room, TimetableEntry, IntegrationSyncRun
from app.integrations.college_source import fetch_timetable, CollegeSourceError


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def sync_official_timetable(app):
    run = IntegrationSyncRun(integration='official_timetable_api', status='Running')
    db.session.add(run)
    db.session.commit()
    run_id = run.id
    try:
        rows = fetch_timetable(app)
        if not rows and not app.config.get('COLLEGE_DATA_ALLOW_EMPTY_SYNC', False):
            raise CollegeSourceError(
                'The official timetable API returned zero rows. Sync is blocked by default; '
                'verify the provider response before explicitly allowing an empty sync.'
            )
        created = updated = 0
        for row in rows:
            department = Department.query.filter_by(code=row['department_code']).first()
            if department is None:
                department = Department(code=row['department_code'], name=row['department_name'])
                db.session.add(department)
                db.session.flush()
            elif department.name != row['department_name']:
                department.name = row['department_name']
            course = Course.query.filter_by(code=row['course_code']).first()
            if course is None:
                course = Course(code=row['course_code'], name=row['course_name'], department_id=department.id,
                                academic_year=row['academic_year'], semester=row['semester'])
                db.session.add(course)
                db.session.flush()
            else:
                course.name = row['course_name']
                course.department_id = department.id
                course.academic_year = row['academic_year']
                course.semester = row['semester']
            room = Room.query.filter_by(code=row['room_code']).first()
            if room is None:
                room = Room(code=row['room_code'], name=row['room_name'], room_type=row['room_type'], capacity=row['capacity'])
                db.session.add(room)
                db.session.flush()
            else:
                room.name = row['room_name']
                room.room_type = row['room_type']
                room.capacity = row['capacity']
                room.is_active = True
            if row['record_id']:
                entry = TimetableEntry.query.filter_by(source_system='official_api', source_record_id=row['record_id']).first()
            else:
                entry = TimetableEntry.query.filter_by(course_id=course.id, day_of_week=row['day_of_week'],
                    start_time=row['start_time'], subject=row['subject'], source_system='official_api').first()
            if entry is None:
                entry = TimetableEntry(course_id=course.id, room_id=room.id, faculty_name=row['faculty_name'],
                    day_of_week=row['day_of_week'], start_time=row['start_time'], end_time=row['end_time'],
                    subject=row['subject'], source_system='official_api', source_record_id=row['record_id'] or None,
                    source_synced_at=datetime.now(timezone.utc))
                db.session.add(entry)
                created += 1
            else:
                entry.course_id = course.id
                entry.room_id = room.id
                entry.faculty_name = row['faculty_name']
                entry.day_of_week = row['day_of_week']
                entry.start_time = row['start_time']
                entry.end_time = row['end_time']
                entry.subject = row['subject']
                entry.source_synced_at = datetime.now(timezone.utc)
                updated += 1
            db.session.flush()
            conflicts = TimetableEntry.query.filter(
                TimetableEntry.id != entry.id,
                TimetableEntry.day_of_week == entry.day_of_week,
                or_(TimetableEntry.room_id == entry.room_id,
                    TimetableEntry.faculty_name.ilike(entry.faculty_name))
            ).all()
            for conflict in conflicts:
                if _overlaps(entry.start_time, entry.end_time, conflict.start_time, conflict.end_time):
                    raise CollegeSourceError(
                        f"Conflict for {row['course_code']} on {entry.day_of_week} {entry.start_time}-{entry.end_time}; "
                        f"overlaps local timetable entry #{conflict.id}. No timetable rows were committed."
                    )
        run.records_received = len(rows)
        run.records_created = created
        run.records_updated = updated
        run.status = 'Success'
        run.message = 'Validated and reconciled official API rows. Source is read-only; no external records were changed.'
        run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        return {'received': len(rows), 'created': created, 'updated': updated, 'status': 'Success'}
    except Exception as exc:
        db.session.rollback()
        # Update the durable attempt record after rolling back every partial timetable write.
        failed_run = db.session.get(IntegrationSyncRun, run_id)
        if failed_run is None:
            failed_run = IntegrationSyncRun(integration='official_timetable_api', started_at=datetime.now(timezone.utc))
            db.session.add(failed_run)
        failed_run.status = 'Failed'
        failed_run.records_received = 0
        failed_run.records_created = 0
        failed_run.records_updated = 0
        failed_run.message = str(exc)[:900]
        failed_run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        raise
