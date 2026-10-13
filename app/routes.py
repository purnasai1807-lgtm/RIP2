import csv
import io
import json
import re
import secrets
import hashlib
import hmac
import time
import threading
import os
import tempfile
from pathlib import Path
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, session, abort, make_response, g
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.exceptions import HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from . import db
from .models import User, Scenario, Impact, Department, Course, Room, TimetableEntry, AuditEvent, ExamSchedule, CampusEvent, AcademicCalendarItem, MaintenanceRequest, AttendanceSession, AttendanceRecord, InventoryItem, Announcement, ServiceRequest, FacultySubstitution, InvigilatorAssignment, InAppNotification, LoginAttempt, IntegrationSyncRun, ImpactFeedback, ScenarioEvidence, CampusActivity, CampusResource, ActivityDependency, ResourceConstraint, CampusIncident, IncidentUpdate, MitigationAction
from .engine import analyze, RULE_VERSION
from .direct_impact import analyze_direct_impacts
from .ripple_impact import analyze_ripple_impacts

DOMAINS = ['Timetable & classrooms', 'Exams & academics', 'Campus facilities', 'College events & clubs', 'Transport & attendance', 'Budget & procurement', 'General college decision']
VARIABLES = ['Date', 'Time', 'Resource', 'Capacity', 'Budget', 'Staffing', 'Delivery time', 'Release date']
ALLOWED_EMAIL_DOMAIN = 'aceec.ac.in'

def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _sha256_json(value):
    return hashlib.sha256(_canonical_json(value).encode('utf-8')).hexdigest()

def _impact_snapshot(item):
    keys = ('level', 'activity', 'description', 'cause', 'severity', 'likelihood',
            'mitigation', 'source', 'parent_activity', 'evidence_ref')
    return {key: getattr(item, key, None) if not isinstance(item, dict) else item.get(key) for key in keys}


def is_eligible_college_email(email):
    """Accept syntactically plausible addresses on the exact ACEEC domain only."""
    normalized = str(email or '').strip().lower()
    if len(normalized) > 254 or normalized.count('@') != 1:
        return False
    local_part, domain = normalized.rsplit('@', 1)
    if domain != ALLOWED_EMAIL_DOMAIN or not local_part or len(local_part) > 64:
        return False
    # A conservative dot-atom check avoids whitespace, control characters, and
    # malformed dotted local parts without adding an unconfigured dependency.
    if local_part.startswith('.') or local_part.endswith('.') or '..' in local_part:
        return False
    return re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local_part) is not None


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def collect_impact_evidence(domain, variable, current_value, proposed_value, context=''):
    """Return only record-backed conflicts, plus explicit data-quality limitations."""
    from .evidence import (parse_interval, overlaps, context_day, context_matches_entry,
                           evidence_item)
    evidence = []
    variable_key = str(variable or '').strip().lower()
    proposed = str(proposed_value or '').strip()
    current = str(current_value or '').strip()
    context_text = str(context or '').strip()
    supported_domains = ('Timetable & classrooms', 'General college decision', 'Campus facilities')

    if domain in supported_domains:
        entries = TimetableEntry.query.order_by(TimetableEntry.day_of_week, TimetableEntry.start_time).limit(1000).all()
        rooms = Room.query.filter_by(is_active=True).all()
        official_entries = [entry for entry in entries if entry.source_system in ('official_api', 'official_csv')]
        now = datetime.now(timezone.utc)
        stale_entries = [entry for entry in official_entries if not entry.source_synced_at or
                         (now - as_utc(entry.source_synced_at)).total_seconds() > 86400]
        if stale_entries:
            evidence.append(evidence_item(1, 'Imported timetable data may be stale',
                f'{len(stale_entries)} imported timetable record(s) have no sync timestamp or were last synced more than 24 hours ago.',
                'A stale snapshot may not represent current room or faculty assignments; this is a data-quality warning, not a confirmed schedule conflict.',
                'Refresh the authorized official API or import a current official export, then reconcile with the timetable owner.',
                'data freshness warning', 'official_timetable_sync_age', 'Medium', 'High'))

        if variable_key == 'resource':
            target_room = next((r for r in rooms if r.code.casefold() == proposed.casefold() or r.name.casefold() == proposed.casefold()), None)
            day = context_day(context_text)
            interval = parse_interval(context_text)
            if target_room and day and interval:
                matching = [e for e in entries if e.room_id == target_room.id and e.day_of_week == day
                            and overlaps(interval, parse_interval(f'{e.start_time}-{e.end_time}'))]
                for entry in matching:
                    evidence.append(evidence_item(1, f'Room conflict: {target_room.code}',
                        f'{target_room.name} is booked for {entry.subject} on {entry.day_of_week}, {entry.start_time}–{entry.end_time}; proposed interval overlaps.',
                        f'The proposed room {target_room.code} and day/time overlap timetable record #{entry.id} ({entry.subject}, faculty {entry.faculty_name}).',
                        'Choose a room with no overlapping booking and sufficient capacity, or reschedule the existing session with coordinator approval.',
                        'college database evidence', f'timetable_entry:{entry.id}'))
            elif target_room:
                evidence.append(evidence_item(1, 'Insufficient details to confirm room availability',
                    f'Room {target_room.code} exists in the local database, but the context must identify a weekday and an unambiguous time interval before a conflict can be confirmed.',
                    'Room identity is known, but overlap cannot be computed without a day and time range.',
                    'Add the weekday and proposed time interval, then rerun the analysis.',
                    'insufficient data', f'room:{target_room.id}', 'Medium', 'Unknown'))
            else:
                evidence.append(evidence_item(1, 'Proposed room not found in local records',
                    f'No active room record exactly matches “{proposed[:80]}”. No room conflict can be confirmed from current records.',
                    'The proposed resource could not be matched to an active room identifier.',
                    'Select a room from the maintained room register or import an authorized, current room list.',
                    'insufficient data', 'room_lookup', 'Medium', 'Unknown'))

        elif variable_key == 'time' and proposed != current:
            day = context_day(context_text)
            proposed_interval = parse_interval(proposed)
            targets = [e for e in entries if context_matches_entry(context_text, e) and (not day or e.day_of_week == day)]
            if targets and proposed_interval:
                for target in targets:
                    for other in entries:
                        if other.id == target.id or other.day_of_week != target.day_of_week:
                            continue
                        same_room = other.room_id == target.room_id
                        same_faculty = other.faculty_name.casefold() == target.faculty_name.casefold()
                        existing = parse_interval(f'{other.start_time}-{other.end_time}')
                        if (same_room or same_faculty) and overlaps(proposed_interval, existing):
                            resource = f'room {target.room.code}' if same_room else f'faculty {target.faculty_name}'
                            evidence.append(evidence_item(1, f'Time conflict: {resource}',
                                f'Proposed time {proposed} for {target.subject} overlaps {other.subject} on {target.day_of_week} ({other.start_time}–{other.end_time}) using the same {resource}.',
                                f'Timetable entry #{target.id} is being moved; entry #{other.id} already occupies the shared {resource} during the proposed interval.',
                                'Choose a non-overlapping interval or an available room/faculty assignment, then rerun the analysis.',
                                'college database evidence', f'timetable_entry:{other.id}'))
                if not any(item.get('source') == 'college database evidence' for item in evidence):
                    evidence.append(evidence_item(1, 'No matching timetable conflict found',
                        f'The proposed interval {proposed} was checked against the matching timetable entry/entries; no same-room or same-faculty overlap was found in the stored records.',
                        'This is a bounded check against the matching local timetable snapshot, not proof that all institutional constraints are satisfied.',
                        'Confirm data freshness and check course, equipment, student-group and transport constraints before publishing.',
                        'college database check', 'timetable_overlap_check', 'Low', 'Medium'))
            else:
                evidence.append(evidence_item(1, 'Insufficient details for exact time-conflict detection',
                    'A time change was proposed, but the system could not identify a matching session and valid time interval from the supplied values/context.',
                    'Exact detection requires a course, subject, room or faculty identifier, a weekday, and a parseable time interval.',
                    'Include the session identifier, weekday, and time as HH:MM or HH:MM-HH:MM, then rerun the analysis.',
                    'insufficient data', 'timetable_session_match', 'Medium', 'Unknown'))

        elif variable_key == 'date' and proposed != current:
            # Dates are checked only when the proposal is a valid ISO date. Exact shared
            # venue matches are conflicts; other same-day records are review warnings.
            try:
                proposed_date = datetime.strptime(proposed, '%Y-%m-%d').date().isoformat()
            except ValueError:
                proposed_date = None
            if not proposed_date:
                evidence.append(evidence_item(1, 'Insufficient date format for calendar check',
                    'The proposed date is not in ISO YYYY-MM-DD format, so date-based record matching was skipped.',
                    'A free-text date cannot be compared reliably with stored ISO calendar dates.',
                    'Enter the proposed date as YYYY-MM-DD and rerun the analysis.',
                    'insufficient data', 'date_format', 'Medium', 'Unknown'))
            else:
                matched_events = [event for event in CampusEvent.query.filter_by(event_date=proposed_date).all()]
                target_text = context_text.casefold()
                target_events = [event for event in CampusEvent.query.all()
                                 if event.title.casefold() in target_text or event.location.casefold() in target_text]
                shared_locations = {event.location.casefold() for event in target_events}
                confirmed_events = [event for event in matched_events if event.location.casefold() in shared_locations]
                for event in confirmed_events:
                    evidence.append(evidence_item(1, f'Venue conflict: {event.title}',
                        f'{event.title} is already planned for {proposed_date} at {event.location}.',
                        f'The proposed date matches an existing campus event in the same location ({event.location}); source record is campus event #{event.id}.',
                        'Choose another date or an approved alternate venue, then confirm with both event owners.',
                        'college database evidence', f'campus_event:{event.id}'))
                other_same_day = [event for event in matched_events if event not in confirmed_events]
                if other_same_day:
                    evidence.append(evidence_item(1, 'Other campus events share the proposed date',
                        f'{len(other_same_day)} event(s) are listed on {proposed_date}, but a shared venue or participant conflict has not been established.',
                        'Same-day scheduling may affect participants or resources, but the stored rows do not by themselves prove a conflict.',
                        'Review venue, audience, organizers and resource requirements with the event coordinator.',
                        'college database check', f'campus_event_date:{proposed_date}', 'Medium', 'Unknown'))
                calendar_items = AcademicCalendarItem.query.filter(AcademicCalendarItem.start_date <= proposed_date).all()
                active_calendar = [item for item in calendar_items if (not item.end_date or item.end_date >= proposed_date)]
                if active_calendar:
                    evidence.append(evidence_item(1, 'Academic calendar entries on proposed date',
                        f'{len(active_calendar)} academic calendar item(s) span {proposed_date}; review is required before confirming the change.',
                        'The proposed date falls within saved academic-calendar intervals; overlap significance depends on item type and audience.',
                        'Review each listed calendar item and its audience/priority before selecting the date.',
                        'college database check', f'academic_calendar:{proposed_date}', 'Medium', 'Unknown'))
                if not confirmed_events and not other_same_day and not active_calendar:
                    evidence.append(evidence_item(1, 'No same-day calendar conflict found in checked records',
                        f'No campus event or academic calendar item was found for {proposed_date} in the local records checked.',
                        'This is a bounded local-data check; it does not prove that external or unsynchronized calendars are clear.',
                        'Confirm official data freshness and check examinations, classes, holidays and external venue bookings.',
                        'college database check', f'calendar_check:{proposed_date}', 'Low', 'Medium'))

        elif variable_key == 'capacity':
            try:
                new_capacity = int(proposed)
            except (TypeError, ValueError):
                new_capacity = None
            target_room = next((r for r in rooms if r.code.casefold() in context_text.casefold() or r.name.casefold() in context_text.casefold()), None)
            if new_capacity is not None and target_room:
                if new_capacity < target_room.capacity:
                    evidence.append(evidence_item(1, f'Capacity change for {target_room.code}',
                        f'{target_room.name} has saved capacity {target_room.capacity}; proposed capacity is {new_capacity}. This is a difference from the room register, not proof of an enrolment shortage.',
                        'The proposed capacity is below the room register value; a real shortage requires enrolment or booking-demand evidence.',
                        'Confirm approved capacity and current enrolment; do not approve until all scheduled sessions fit the revised limit.',
                        'college database check', f'room:{target_room.id}', 'Medium', 'Medium'))
                else:
                    evidence.append(evidence_item(1, f'Capacity value checked for {target_room.code}',
                        f'Proposed capacity {new_capacity} is not below the stored room capacity {target_room.capacity}; no shortage is established by this comparison.',
                        'The proposed value was compared to the exact room record, but this does not establish student demand or regulatory suitability.',
                        'Verify approved room capacity and enrolment before updating the official register.',
                        'college database check', f'room:{target_room.id}', 'Low', 'Medium'))
            else:
                evidence.append(evidence_item(1, 'Insufficient data for capacity impact',
                    'A numeric capacity and exact room identifier in the context are required; student enrolment/demand records are not currently joined to this check.',
                    'Without a target room and demand count, the system cannot assert that a capacity change causes a shortage.',
                    'Identify the room and connect an authorized enrolment/demand source before approving the change.',
                    'insufficient data', 'capacity_room_match', 'Medium', 'Unknown'))

    if domain == 'Exams & academics' or 'exam' in context_text.casefold():
        exams = ExamSchedule.query.order_by(ExamSchedule.exam_date, ExamSchedule.start_time).limit(1000).all()
        if exams:
            if variable_key == 'date' and proposed != current:
                try:
                    proposed_exam_date = datetime.strptime(proposed, '%Y-%m-%d').date().isoformat()
                except ValueError:
                    proposed_exam_date = None
                context_key = context_text.casefold()
                target_exams = [exam for exam in exams if
                                exam.title.casefold() in context_key or
                                exam.course.code.casefold() in context_key or
                                exam.course.name.casefold() in context_key]
                if proposed_exam_date and target_exams:
                    found_conflict = False
                    for target in target_exams:
                        for other in exams:
                            if other.id == target.id or other.exam_date != proposed_exam_date:
                                continue
                            same_hall = other.room_id == target.room_id
                            same_course = other.course_id == target.course_id
                            time_overlap = overlaps(parse_interval(f'{target.start_time}-{target.end_time}'),
                                                    parse_interval(f'{other.start_time}-{other.end_time}'))
                            if time_overlap and (same_hall or same_course):
                                found_conflict = True
                                resource = 'hall' if same_hall else 'course'
                                evidence.append(evidence_item(1, f'Exam date/time conflict: {target.title}',
                                    f'Moving {target.title} to {proposed_exam_date} would overlap {other.title} ({other.exam_date}, {other.start_time}–{other.end_time}) for the same {resource}.',
                                    f'Exam record #{target.id} is matched from the scenario context and overlaps record #{other.id} on the same hall or course at the proposed date/time.',
                                    'Choose a date/time with no same-hall or same-course overlap and verify invigilator assignments and student paper gaps.',
                                    'college database evidence', f'exam_schedule:{other.id}'))
                    if not found_conflict:
                        evidence.append(evidence_item(1, 'No matching exam conflict found in checked records',
                            f'The proposed date {proposed_exam_date} was checked for the matched exam(s); no same-hall or same-course time overlap was found in stored exam records.',
                            'This is a bounded check against local exam rows and does not validate all student paper gaps, invigilators or unsynchronized calendars.',
                            'Verify the official examination calendar, invigilator assignments and student minimum-gap policy before approval.',
                            'college database check', f'exam_date_check:{proposed_exam_date}', 'Low', 'Medium'))
                else:
                    evidence.append(evidence_item(1, 'Insufficient details for exact exam-date check',
                        'The proposed date is not ISO YYYY-MM-DD or the scenario context does not identify a stored exam by title/course code/name.',
                        'Without a unique target exam, the system cannot safely decide which record is being moved.',
                        'Use the exact exam title or course identifier and a YYYY-MM-DD proposed date, then rerun the analysis.',
                        'insufficient data', 'exam_date_target', 'Medium', 'Unknown'))
            else:
                evidence.append(evidence_item(1, 'Exam calendar available for review',
                    f'{len(exams)} exam schedule record(s) exist locally; the proposal must identify a specific exam and proposed date/time before a direct conflict can be confirmed.',
                    'Exam dates, halls and invigilators are shared constraints, but generic scenario text does not uniquely identify an exam to move.',
                    'Identify the exact exam and compare date, time, room capacity, invigilators and student paper gaps before approval.',
                    'college database context', 'exam_schedule_collection', 'Medium', 'Unknown'))
        else:
            evidence.append(evidence_item(1, 'No exam schedule records available',
                'The local database contains no exam schedule records to support an evidence-backed exam conflict check.',
                'Without exam records, downstream exam impacts remain hypotheses rather than confirmed conflicts.',
                'Import or enter an authorized current exam calendar before relying on this analysis.',
                'insufficient data', 'exam_schedule_collection', 'Medium', 'Unknown'))
    return evidence


def register_routes(app):
    app.jinja_env.globals['csrf_token'] = csrf_token
    app.jinja_env.globals['domains'] = DOMAINS
    app.jinja_env.globals['variables'] = VARIABLES

    @app.get('/dataset-analysis')
    @login_required
    def dataset_analysis():
        from .dataset_engine import dataset_report
        selected_variant = (request.args.get('variant') or 'V1').upper()
        if selected_variant not in {'V1', 'V2', 'V3'}:
            selected_variant = 'V1'
        report = dataset_report(selected_variant)
        return render_template('dataset_analysis.html', selected_variant=selected_variant,
                               report=report, result=report.get('analysis', {}),
                               validation=report.get('validation', {}))

    @app.get('/api/dataset-analysis')
    @login_required
    def api_dataset_analysis():
        from .dataset_engine import dataset_report
        selected_variant = (request.args.get('variant') or 'V1').upper()
        if selected_variant not in {'V1', 'V2', 'V3'}:
            return make_response(json.dumps({'ok': False, 'error': 'variant must be V1, V2, or V3'}),
                                 400, {'Content-Type': 'application/json; charset=utf-8'})
        payload = dataset_report(selected_variant)
        response = make_response(json.dumps(payload, ensure_ascii=False, indent=2), 200 if payload.get('ok') else 422)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/dataset-download.zip')
    @login_required
    def dataset_download():
        from pathlib import Path
        import zipfile
        from .dataset_engine import DATA_DIR, TABLES
        root = Path(DATA_DIR)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name in (*[f'{table}.csv' for table in TABLES], 'incident.json',
                         'README.md', 'START_HERE_STUDENTS.md', 'ACRONYMS_AND_DATA_GLOSSARY.md',
                         'optimization_rules.md', 'dataset_manifest.json'):
                file_path = root / name
                if file_path.is_file():
                    archive.write(file_path, arcname=name)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = 'attachment; filename="The_Ripple_Dataset_imported.zip"'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    INCIDENT_TYPES = ('Power', 'Network', 'Water', 'Fire/Safety', 'Facilities', 'Transport', 'Staffing', 'Other')
    INCIDENT_SEVERITIES = ('Low', 'Medium', 'High', 'Critical')
    INCIDENT_STATUSES = ('Reported', 'Investigating', 'Monitoring', 'Resolved', 'False alarm')

    def incident_payload(item, include_updates=False):
        data = {
            'id': item.id, 'incident_code': item.incident_code, 'title': item.title,
            'description': item.description, 'incident_type': item.incident_type,
            'severity': item.severity, 'status': item.status, 'location': item.location,
            'resource_id': item.resource_id, 'resource_code': item.resource.code if item.resource else None,
            'activity_id': item.activity_id, 'activity_code': item.activity.code if item.activity else None,
            'reported_by': item.reporter.name if item.reporter else None,
            'reported_at': as_utc(item.reported_at).isoformat() if item.reported_at else None,
            'started_at': as_utc(item.started_at).isoformat() if item.started_at else None,
            'estimated_duration_minutes': item.estimated_duration_minutes,
            'resolved_at': as_utc(item.resolved_at).isoformat() if item.resolved_at else None,
            'last_updated_at': as_utc(item.last_updated_at).isoformat() if item.last_updated_at else None,
        }
        if include_updates:
            data['updates'] = [{'id': u.id, 'update_type': u.update_type, 'previous_status': u.previous_status,
                'new_status': u.new_status, 'previous_duration_minutes': u.previous_duration_minutes,
                'new_duration_minutes': u.new_duration_minutes, 'note': u.note,
                'user': u.user.name if u.user else None,
                'created_at': as_utc(u.created_at).isoformat() if u.created_at else None} for u in item.updates]
        return data

    def parse_incident_datetime(raw, field_name):
        if raw in (None, ''):
            return None
        try:
            value = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f'{field_name} must be a valid ISO date/time.')
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def incident_input(data, existing=None):
        title = str(data.get('title', existing.title if existing else '')).strip()
        description = str(data.get('description', existing.description if existing else '')).strip()
        incident_type = str(data.get('incident_type', existing.incident_type if existing else 'Other')).strip()
        severity = str(data.get('severity', existing.severity if existing else 'Medium')).strip()
        location = str(data.get('location', existing.location if existing else '')).strip()
        status = str(data.get('status', existing.status if existing else 'Reported')).strip()
        if not title or len(title) > 160: raise ValueError('Title is required and must be 160 characters or fewer.')
        if not description or len(description) > 10000: raise ValueError('Description is required and must be 10000 characters or fewer.')
        if incident_type not in INCIDENT_TYPES: raise ValueError('Choose a valid incident type.')
        if severity not in INCIDENT_SEVERITIES: raise ValueError('Choose a valid severity.')
        if status not in INCIDENT_STATUSES: raise ValueError('Choose a valid status.')
        if len(location) > 160: raise ValueError('Location must be 160 characters or fewer.')
        def optional_id(key, current):
            raw = data.get(key, current)
            if raw in (None, ''): return None
            try: val = int(raw)
            except (ValueError, TypeError): raise ValueError(f'{key} must be a valid record ID.')
            if val < 1: raise ValueError(f'{key} must be a positive record ID.')
            return val
        resource_id = optional_id('resource_id', existing.resource_id if existing else None)
        activity_id = optional_id('activity_id', existing.activity_id if existing else None)
        if resource_id and not db.session.get(CampusResource, resource_id): raise ValueError('Selected resource does not exist.')
        if activity_id and not db.session.get(CampusActivity, activity_id): raise ValueError('Selected activity does not exist.')
        duration_raw = data.get('estimated_duration_minutes', existing.estimated_duration_minutes if existing else None)
        if duration_raw in (None, ''): duration = None
        else:
            try: duration = int(duration_raw)
            except (ValueError, TypeError): raise ValueError('Estimated duration must be whole minutes.')
            if duration < 1 or duration > 525600: raise ValueError('Estimated duration must be between 1 minute and 365 days.')
        started = parse_incident_datetime(data.get('started_at', None), 'Incident start time') if 'started_at' in data else (existing.started_at if existing else None)
        if started and started > datetime.now(timezone.utc) + timedelta(minutes=5): raise ValueError('Incident start time cannot be in the future.')
        return dict(title=title, description=description, incident_type=incident_type, severity=severity,
                    status=status, location=location, resource_id=resource_id, activity_id=activity_id,
                    estimated_duration_minutes=duration, started_at=started)

    @app.get('/incidents')
    @login_required
    def incidents_page():
        query = CampusIncident.query
        status_filter = request.args.get('status', '').strip()
        severity_filter = request.args.get('severity', '').strip()
        search_term = request.args.get('q', '').strip()[:100]
        if status_filter in INCIDENT_STATUSES: query = query.filter_by(status=status_filter)
        if severity_filter in INCIDENT_SEVERITIES: query = query.filter_by(severity=severity_filter)
        if search_term:
            query = query.filter(or_(CampusIncident.title.ilike(f'%{search_term}%'), CampusIncident.incident_code.ilike(f'%{search_term}%'), CampusIncident.location.ilike(f'%{search_term}%')))
        incidents = query.order_by(CampusIncident.reported_at.desc()).limit(200).all()
        return render_template('incidents.html', incidents=incidents, can_manage=current_user.role in ('coordinator','admin'),
            status_filter=status_filter, severity_filter=severity_filter, q=search_term,
            statuses=INCIDENT_STATUSES, severities=INCIDENT_SEVERITIES, types=INCIDENT_TYPES,
            resources=CampusResource.query.order_by(CampusResource.name).all(), activities=CampusActivity.query.order_by(CampusActivity.name).all())

    @app.post('/incidents')
    @login_required
    def create_incident():
        require_roles('coordinator', 'admin')
        data = request.form.to_dict()
        try: fields = incident_input(data)
        except ValueError as exc:
            flash(str(exc), 'error'); return redirect(url_for('incidents_page'))
        code = (data.get('incident_code') or '').strip().upper() or f'INC-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}'
        if len(code) > 24 or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,23}', code):
            flash('Incident code must be 3–24 letters, numbers, hyphens or underscores.', 'error'); return redirect(url_for('incidents_page'))
        item = CampusIncident(incident_code=code, reported_by_id=current_user.id, reported_at=utcnow(), **fields)
        if item.status in ('Resolved', 'False alarm'): item.resolved_at = utcnow()
        db.session.add(item); db.session.flush()
        db.session.add(IncidentUpdate(incident_id=item.id, user_id=current_user.id, update_type='Created', new_status=item.status, new_duration_minutes=item.estimated_duration_minutes, note='Incident reported'))
        record_audit('campus_incident_created', 'CampusIncident', item.id, f'{code}: {item.severity} {item.incident_type}')
        db.session.commit()
        flash(f'Incident {code} reported.', 'success')
        return redirect(url_for('incident_detail', incident_id=item.id))

    @app.get('/incidents/<int:incident_id>')
    @login_required
    def incident_detail(incident_id):
        item = db.session.get(CampusIncident, incident_id)
        if not item: abort(404)
        return render_template('incident_detail.html', incident=item, can_manage=current_user.role in ('coordinator','admin'), statuses=INCIDENT_STATUSES)

    @app.get('/incidents/<int:incident_id>/direct-impacts')
    @login_required
    def incident_direct_impacts(incident_id):
        item = db.session.get(CampusIncident, incident_id)
        if not item:
            abort(404)
        dependencies = ActivityDependency.query.order_by(ActivityDependency.id).limit(5000).all()
        constraints = ResourceConstraint.query.order_by(ResourceConstraint.id).limit(5000).all()
        report = analyze_direct_impacts(item, dependencies, constraints)
        return render_template('direct_impacts.html', incident=item, report=report)

    @app.get('/api/incidents/<int:incident_id>/direct-impacts')
    @login_required
    def api_incident_direct_impacts(incident_id):
        item = db.session.get(CampusIncident, incident_id)
        if not item:
            return {'error': 'Incident not found.'}, 404
        dependencies = ActivityDependency.query.order_by(ActivityDependency.id).limit(5000).all()
        constraints = ResourceConstraint.query.order_by(ResourceConstraint.id).limit(5000).all()
        return analyze_direct_impacts(item, dependencies, constraints), 200

    @app.get('/incidents/<int:incident_id>/ripple-analysis')
    @login_required
    def incident_ripple_analysis(incident_id):
        item = db.session.get(CampusIncident, incident_id)
        if not item:
            abort(404)
        dependencies = ActivityDependency.query.order_by(ActivityDependency.id).limit(5000).all()
        constraints = ResourceConstraint.query.order_by(ResourceConstraint.id).limit(5000).all()
        try:
            max_depth = int(request.args.get('depth', '5'))
        except (TypeError, ValueError):
            max_depth = 5
        report = analyze_ripple_impacts(item, dependencies, constraints, max_depth=max_depth)
        return render_template('ripple_analysis.html', incident=item, report=report)

    @app.get('/api/incidents/<int:incident_id>/ripple-analysis')
    @login_required
    def api_incident_ripple_analysis(incident_id):
        item = db.session.get(CampusIncident, incident_id)
        if not item:
            return {'error': 'Incident not found.'}, 404
        dependencies = ActivityDependency.query.order_by(ActivityDependency.id).limit(5000).all()
        constraints = ResourceConstraint.query.order_by(ResourceConstraint.id).limit(5000).all()
        try:
            max_depth = int(request.args.get('depth', '5'))
        except (TypeError, ValueError):
            max_depth = 5
        return analyze_ripple_impacts(item, dependencies, constraints, max_depth=max_depth), 200

    @app.post('/incidents/<int:incident_id>/update')
    @login_required
    def update_incident(incident_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(CampusIncident, incident_id)
        if not item: abort(404)
        data = request.form.to_dict()
        try: fields = incident_input(data, item)
        except ValueError as exc:
            flash(str(exc), 'error'); return redirect(url_for('incident_detail', incident_id=item.id))
        note = str(data.get('note', '')).strip()
        if len(note) > 2000:
            flash('Update note must be 2000 characters or fewer.', 'error'); return redirect(url_for('incident_detail', incident_id=item.id))
        old_status, old_duration = item.status, item.estimated_duration_minutes
        item.title = fields['title']; item.description = fields['description']; item.incident_type = fields['incident_type']
        item.severity = fields['severity']; item.status = fields['status']; item.location = fields['location']
        item.resource_id = fields['resource_id']; item.activity_id = fields['activity_id']
        item.estimated_duration_minutes = fields['estimated_duration_minutes']; item.started_at = fields['started_at']
        item.resolved_at = utcnow() if item.status in ('Resolved', 'False alarm') else None
        item.last_updated_at = utcnow()
        update_type = 'Status' if old_status != item.status else ('ETA' if old_duration != item.estimated_duration_minutes else 'Update')
        db.session.add(IncidentUpdate(incident_id=item.id, user_id=current_user.id, update_type=update_type,
            previous_status=old_status, new_status=item.status, previous_duration_minutes=old_duration,
            new_duration_minutes=item.estimated_duration_minutes, note=note))
        record_audit('campus_incident_updated', 'CampusIncident', item.id, f'{item.incident_code}: {old_status} -> {item.status}')
        db.session.commit(); flash('Incident updated and history recorded.', 'success')
        return redirect(url_for('incident_detail', incident_id=item.id))

    @app.get('/api/incidents')
    @login_required
    def api_incidents():
        query = CampusIncident.query
        status_filter = request.args.get('status', '').strip()
        severity_filter = request.args.get('severity', '').strip()
        if status_filter in INCIDENT_STATUSES: query = query.filter_by(status=status_filter)
        if severity_filter in INCIDENT_SEVERITIES: query = query.filter_by(severity=severity_filter)
        return {'items': [incident_payload(i) for i in query.order_by(CampusIncident.reported_at.desc()).limit(200).all()]}, 200

    @app.post('/api/incidents')
    @login_required
    def api_create_incident():
        require_roles('coordinator', 'admin')
        data = request.get_json(silent=True) or {}
        try: fields = incident_input(data)
        except ValueError as exc: return {'error': str(exc)}, 400
        code = str(data.get('incident_code') or '').strip().upper() or f'INC-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}'
        if len(code) > 24 or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,23}', code): return {'error':'Incident code must be 3–24 letters, numbers, hyphens or underscores.'}, 400
        item = CampusIncident(incident_code=code, reported_by_id=current_user.id, reported_at=utcnow(), **fields)
        if item.status in ('Resolved','False alarm'): item.resolved_at = utcnow()
        db.session.add(item); db.session.flush()
        db.session.add(IncidentUpdate(incident_id=item.id, user_id=current_user.id, update_type='Created', new_status=item.status, new_duration_minutes=item.estimated_duration_minutes, note='Incident reported via API'))
        record_audit('campus_incident_created', 'CampusIncident', item.id, f'{code}: {item.severity} {item.incident_type}')
        db.session.commit(); return incident_payload(item, True), 201

    @app.get('/api/incidents/<int:incident_id>')
    @login_required
    def api_incident_detail(incident_id):
        item = db.session.get(CampusIncident, incident_id)
        if not item: return {'error':'Incident not found.'}, 404
        return incident_payload(item, True), 200

    @app.patch('/api/incidents/<int:incident_id>')
    @login_required
    def api_update_incident(incident_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(CampusIncident, incident_id)
        if not item: return {'error':'Incident not found.'}, 404
        data = request.get_json(silent=True) or {}
        try: fields = incident_input(data, item)
        except ValueError as exc: return {'error':str(exc)}, 400
        note = str(data.get('note', '')).strip()
        if len(note) > 2000: return {'error':'Update note must be 2000 characters or fewer.'}, 400
        old_status, old_duration = item.status, item.estimated_duration_minutes
        for key, value in fields.items(): setattr(item, key, value)
        item.resolved_at = utcnow() if item.status in ('Resolved','False alarm') else None
        item.last_updated_at = utcnow()
        kind = 'Status' if old_status != item.status else ('ETA' if old_duration != item.estimated_duration_minutes else 'Update')
        db.session.add(IncidentUpdate(incident_id=item.id, user_id=current_user.id, update_type=kind,
            previous_status=old_status, new_status=item.status, previous_duration_minutes=old_duration,
            new_duration_minutes=item.estimated_duration_minutes, note=note))
        record_audit('campus_incident_updated', 'CampusIncident', item.id, f'{item.incident_code}: {old_status} -> {item.status}')
        db.session.commit(); return incident_payload(item, True), 200

    @app.get('/campus-model')
    @login_required
    def campus_model():
        activities = CampusActivity.query.order_by(CampusActivity.name).all()
        resources = CampusResource.query.order_by(CampusResource.name).all()
        dependencies = ActivityDependency.query.order_by(ActivityDependency.id.desc()).all()
        constraints = ResourceConstraint.query.order_by(ResourceConstraint.id.desc()).all()
        can_manage = current_user.role in ('coordinator', 'admin')
        return render_template('campus_model.html', activities=activities, resources=resources,
                               dependencies=dependencies, constraints=constraints, can_manage=can_manage)

    @app.post('/campus-model/activities')
    @login_required
    def add_campus_activity():
        require_roles('coordinator', 'admin')
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        attendance = request.form.get('expected_attendance', '0').strip()
        if not code or not name or len(code) > 32 or not attendance.isdigit() or int(attendance) > 100000:
            flash('Enter a unique code, activity name, and valid attendance (0–100000).', 'error')
            return redirect(url_for('campus_model'))
        start_raw = request.form.get('start_at', '').strip()
        end_raw = request.form.get('end_at', '').strip()
        try:
            start_at = datetime.fromisoformat(start_raw) if start_raw else None
            end_at = datetime.fromisoformat(end_raw) if end_raw else None
        except ValueError:
            flash('Use valid start and end date/time values.', 'error')
            return redirect(url_for('campus_model'))
        if start_at and end_at and end_at <= start_at:
            flash('Activity end time must be later than its start time.', 'error')
            return redirect(url_for('campus_model'))
        activity_type = request.form.get('activity_type', 'Other')
        criticality = request.form.get('criticality', 'Medium')
        status = request.form.get('status', 'Scheduled')
        if activity_type not in ('Lecture', 'Exam', 'Workshop', 'Review', 'Event', 'Service', 'Other') or criticality not in ('Low', 'Medium', 'High', 'Critical') or status not in ('Scheduled', 'In progress', 'Completed', 'Cancelled'):
            flash('Choose valid activity type, criticality, and status values.', 'error')
            return redirect(url_for('campus_model'))
        item = CampusActivity(code=code, name=name[:140], activity_type=activity_type,
            location=request.form.get('location', '').strip()[:120], expected_attendance=int(attendance),
            criticality=criticality, status=status, start_at=start_at, end_at=end_at,
            notes=request.form.get('notes', '').strip()[:2000])
        db.session.add(item)
        try:
            db.session.flush()
            record_audit('campus_activity_created', 'CampusActivity', item.id, f'Created activity {code}')
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('That activity code already exists. Use a unique code.', 'error')
            return redirect(url_for('campus_model'))
        flash('Campus activity saved.', 'success')
        return redirect(url_for('campus_model'))

    @app.post('/campus-model/resources')
    @login_required
    def add_campus_resource():
        require_roles('coordinator', 'admin')
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        capacity = request.form.get('capacity', '0').strip()
        if not code or not name or len(code) > 32 or not capacity.isdigit() or int(capacity) > 100000:
            flash('Enter a unique code, resource name, and valid capacity (0–100000).', 'error')
            return redirect(url_for('campus_model'))
        resource_type = request.form.get('resource_type', 'Other')
        status = request.form.get('status', 'Unknown')
        if resource_type not in ('Room', 'Equipment', 'Infrastructure', 'Network', 'Power', 'Transport', 'Staff', 'Service', 'Other') or status not in ('Available', 'Limited', 'Unavailable', 'Under maintenance', 'Unknown'):
            flash('Choose a valid resource type and status.', 'error')
            return redirect(url_for('campus_model'))
        item = CampusResource(code=code, name=name[:140], resource_type=resource_type,
            location=request.form.get('location', '').strip()[:120], capacity=int(capacity),
            status=status, notes=request.form.get('notes', '').strip()[:2000])
        db.session.add(item)
        try:
            db.session.flush()
            record_audit('campus_resource_created', 'CampusResource', item.id, f'Created resource {code}')
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('That resource code already exists. Use a unique code.', 'error')
            return redirect(url_for('campus_model'))
        flash('Campus resource saved.', 'success')
        return redirect(url_for('campus_model'))

    @app.post('/campus-model/dependencies')
    @login_required
    def add_activity_dependency():
        require_roles('coordinator', 'admin')
        source_id = request.form.get('source_activity_id', type=int)
        target_kind = request.form.get('target_kind', 'resource')
        target_id = request.form.get('target_id', type=int)
        source = db.session.get(CampusActivity, source_id) if source_id else None
        target = (db.session.get(CampusResource, target_id) if target_kind == 'resource' else
                  db.session.get(CampusActivity, target_id) if target_kind == 'activity' else None)
        if not source or not target or (target_kind == 'activity' and source.id == target.id):
            flash('Choose a valid source activity and a different target resource/activity.', 'error')
            return redirect(url_for('campus_model'))
        dependency_type = request.form.get('dependency_type', 'requires')
        importance = request.form.get('importance', 'Required')
        if dependency_type not in ('requires', 'uses', 'follows', 'supports') or importance not in ('Required', 'Preferred', 'Optional'):
            flash('Choose a valid dependency relationship and importance.', 'error')
            return redirect(url_for('campus_model'))
        # A source activity points to what it depends on. Reject links that would
        # introduce a directed cycle, which would make ripple explanations ambiguous.
        if target_kind == 'activity':
            pending, visited = [target.id], set()
            while pending:
                node_id = pending.pop()
                if node_id == source.id:
                    flash('This dependency would create a cycle. Remove or change an existing link first.', 'error')
                    return redirect(url_for('campus_model'))
                if node_id in visited:
                    continue
                visited.add(node_id)
                pending.extend(d.target_activity_id for d in ActivityDependency.query.filter_by(source_activity_id=node_id).all() if d.target_activity_id is not None)
        values = dict(source_activity_id=source.id, dependency_type=dependency_type,
                      importance=importance, notes=request.form.get('notes', '').strip()[:500])
        if target_kind == 'resource': values['target_resource_id'] = target.id
        else: values['target_activity_id'] = target.id
        duplicate = ActivityDependency.query.filter_by(**values).first()
        if duplicate:
            flash('That dependency already exists.', 'error')
            return redirect(url_for('campus_model'))
        item = ActivityDependency(**values)
        db.session.add(item)
        db.session.flush()
        record_audit('activity_dependency_created', 'ActivityDependency', item.id, f'{source.code} depends on {target.code}')
        db.session.commit()
        flash('Dependency saved. It can now be used by impact analysis.', 'success')
        return redirect(url_for('campus_model'))

    @app.post('/campus-model/constraints')
    @login_required
    def add_resource_constraint():
        require_roles('coordinator', 'admin')
        resource = db.session.get(CampusResource, request.form.get('resource_id', type=int))
        constraint_type = request.form.get('constraint_type', '').strip()[:32]
        limit_value = request.form.get('limit_value', '').strip()[:120]
        allowed_constraint_types = ('Capacity', 'Availability', 'Power rating', 'Operating hours', 'Safety', 'Equipment count', 'Other')
        if not resource or constraint_type not in allowed_constraint_types or not limit_value:
            flash('Choose a valid resource and constraint type, and enter the limit.', 'error')
            return redirect(url_for('campus_model'))
        operator = request.form.get('operator', '<=')
        if operator not in ('<=', '>=', '=', '<', '>'):
            flash('Choose a valid comparison operator.', 'error')
            return redirect(url_for('campus_model'))
        item = ResourceConstraint(resource_id=resource.id, constraint_type=constraint_type, operator=operator,
            limit_value=limit_value, unit=request.form.get('unit', '').strip()[:24],
            is_hard_constraint=request.form.get('is_hard_constraint') == 'yes', notes=request.form.get('notes', '').strip()[:500])
        db.session.add(item)
        db.session.flush()
        record_audit('resource_constraint_created', 'ResourceConstraint', item.id, f'Added {constraint_type} constraint to {resource.code}')
        db.session.commit()
        flash('Resource constraint saved.', 'success')
        return redirect(url_for('campus_model'))

    @app.route('/campus-model/activities/<int:activity_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_campus_activity(activity_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(CampusActivity, activity_id)
        if not item:
            abort(404)
        types = ('Lecture', 'Exam', 'Workshop', 'Review', 'Event', 'Service', 'Other')
        criticalities = ('Low', 'Medium', 'High', 'Critical')
        statuses = ('Scheduled', 'In progress', 'Completed', 'Cancelled')
        if request.method == 'POST':
            code = request.form.get('code', '').strip().upper()
            name = request.form.get('name', '').strip()
            attendance = request.form.get('expected_attendance', '').strip()
            activity_type = request.form.get('activity_type', '')
            criticality = request.form.get('criticality', '')
            status = request.form.get('status', '')
            try:
                start_at = datetime.fromisoformat(request.form['start_at']) if request.form.get('start_at', '').strip() else None
                end_at = datetime.fromisoformat(request.form['end_at']) if request.form.get('end_at', '').strip() else None
            except ValueError:
                flash('Enter valid start and end date/time values.', 'error')
                return redirect(url_for('edit_campus_activity', activity_id=item.id))
            if (not code or len(code) > 32 or not name or len(name) > 140 or not attendance.isdigit()
                    or int(attendance) > 100000 or activity_type not in types or criticality not in criticalities
                    or status not in statuses or (start_at and end_at and end_at <= start_at)):
                flash('Check the activity fields; values, attendance, and time range must be valid.', 'error')
                return redirect(url_for('edit_campus_activity', activity_id=item.id))
            item.code, item.name, item.activity_type = code, name, activity_type
            item.location = request.form.get('location', '').strip()[:120]
            item.expected_attendance, item.criticality, item.status = int(attendance), criticality, status
            item.start_at, item.end_at = start_at, end_at
            item.notes = request.form.get('notes', '').strip()[:2000]
            try:
                db.session.flush()
                record_audit('campus_activity_updated', 'CampusActivity', item.id, f'Updated activity {code}')
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('That activity code is already used by another activity.', 'error')
                return redirect(url_for('edit_campus_activity', activity_id=item.id))
            flash('Campus activity updated.', 'success')
            return redirect(url_for('campus_model'))
        fields = [
            {'name':'code','label':'Activity code','value':item.code,'required':True,'maxlength':32},
            {'name':'name','label':'Activity name','value':item.name,'required':True,'maxlength':140},
            {'name':'activity_type','label':'Type','value':item.activity_type,'options':types},
            {'name':'location','label':'Location','value':item.location,'maxlength':120},
            {'name':'start_at','label':'Start date/time','value':item.start_at.strftime('%Y-%m-%dT%H:%M') if item.start_at else '', 'kind':'datetime-local'},
            {'name':'end_at','label':'End date/time','value':item.end_at.strftime('%Y-%m-%dT%H:%M') if item.end_at else '', 'kind':'datetime-local'},
            {'name':'expected_attendance','label':'Expected attendance','value':item.expected_attendance,'kind':'number','min':0,'required':True},
            {'name':'criticality','label':'Criticality','value':item.criticality,'options':criticalities},
            {'name':'status','label':'Status','value':item.status,'options':statuses},
            {'name':'notes','label':'Notes','value':item.notes,'kind':'textarea','maxlength':2000},
        ]
        return render_template('campus_record_edit.html', record_type='activity', fields=fields)

    @app.route('/campus-model/resources/<int:resource_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_campus_resource(resource_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(CampusResource, resource_id)
        if not item:
            abort(404)
        types = ('Room', 'Equipment', 'Infrastructure', 'Network', 'Power', 'Transport', 'Staff', 'Service', 'Other')
        statuses = ('Available', 'Limited', 'Unavailable', 'Under maintenance', 'Unknown')
        if request.method == 'POST':
            code = request.form.get('code', '').strip().upper()
            name = request.form.get('name', '').strip()
            capacity = request.form.get('capacity', '').strip()
            resource_type = request.form.get('resource_type', '')
            status = request.form.get('status', '')
            if (not code or len(code) > 32 or not name or len(name) > 140 or not capacity.isdigit()
                    or int(capacity) > 100000 or resource_type not in types or status not in statuses):
                flash('Check the resource fields and enter a valid capacity (0–100000).', 'error')
                return redirect(url_for('edit_campus_resource', resource_id=item.id))
            item.code, item.name, item.resource_type = code, name, resource_type
            item.location = request.form.get('location', '').strip()[:120]
            item.capacity, item.status = int(capacity), status
            item.notes = request.form.get('notes', '').strip()[:2000]
            try:
                db.session.flush()
                record_audit('campus_resource_updated', 'CampusResource', item.id, f'Updated resource {code}')
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('That resource code is already used by another resource.', 'error')
                return redirect(url_for('edit_campus_resource', resource_id=item.id))
            flash('Campus resource updated.', 'success')
            return redirect(url_for('campus_model'))
        fields = [
            {'name':'code','label':'Resource code','value':item.code,'required':True,'maxlength':32},
            {'name':'name','label':'Resource name','value':item.name,'required':True,'maxlength':140},
            {'name':'resource_type','label':'Type','value':item.resource_type,'options':types},
            {'name':'location','label':'Location','value':item.location,'maxlength':120},
            {'name':'capacity','label':'Capacity','value':item.capacity,'kind':'number','min':0,'required':True},
            {'name':'status','label':'Status','value':item.status,'options':statuses},
            {'name':'notes','label':'Notes','value':item.notes,'kind':'textarea','maxlength':2000},
        ]
        return render_template('campus_record_edit.html', record_type='resource', fields=fields)

    @app.post('/campus-model/dependencies/<int:dependency_id>/delete')
    @login_required
    def delete_activity_dependency(dependency_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(ActivityDependency, dependency_id)
        if not item:
            abort(404)
        record_audit('activity_dependency_deleted', 'ActivityDependency', item.id, 'Deleted campus dependency')
        db.session.delete(item)
        db.session.commit()
        flash('Dependency deleted.', 'success')
        return redirect(url_for('campus_model'))

    @app.post('/campus-model/constraints/<int:constraint_id>/delete')
    @login_required
    def delete_resource_constraint(constraint_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(ResourceConstraint, constraint_id)
        if not item:
            abort(404)
        record_audit('resource_constraint_deleted', 'ResourceConstraint', item.id, 'Deleted resource constraint')
        db.session.delete(item)
        db.session.commit()
        flash('Resource constraint deleted.', 'success')
        return redirect(url_for('campus_model'))

    @app.post('/campus-model/activities/<int:activity_id>/delete')
    @login_required
    def delete_campus_activity(activity_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(CampusActivity, activity_id)
        if not item:
            abort(404)
        code = item.code
        record_audit('campus_activity_deleted', 'CampusActivity', item.id, f'Deleted activity {code}')
        db.session.delete(item)
        db.session.commit()
        flash('Activity deleted; its dependency links were removed.', 'success')
        return redirect(url_for('campus_model'))

    @app.post('/campus-model/resources/<int:resource_id>/delete')
    @login_required
    def delete_campus_resource(resource_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(CampusResource, resource_id)
        if not item:
            abort(404)
        code = item.code
        record_audit('campus_resource_deleted', 'CampusResource', item.id, f'Deleted resource {code}')
        db.session.delete(item)
        db.session.commit()
        flash('Resource deleted; its dependency links and constraints were removed.', 'success')
        return redirect(url_for('campus_model'))

    @app.before_request
    def begin_request_timing():
        g.request_started_at = time.perf_counter()

    @app.before_request
    def protect_post_requests():
        if request.method == 'POST':
            # Browser forms use the hidden field; JSON clients may send the same
            # session-bound token in X-CSRF-Token. Do not exempt JSON writes.
            submitted = request.form.get('_csrf_token', '') or request.headers.get('X-CSRF-Token', '')
            expected = session.get('_csrf_token', '')
            if not expected or not secrets.compare_digest(submitted, expected):
                abort(400, description='Security token expired or missing. Refresh the page and try again.')

    @app.after_request
    def security_headers(response):
        started = getattr(g, 'request_started_at', None)
        if started is not None:
            # Log endpoint name only: reset-token URLs and query parameters must not enter logs.
            app.logger.info('http_request endpoint=%s method=%s status=%s duration_ms=%.2f',
                            request.endpoint or 'unknown', request.method, response.status_code,
                            (time.perf_counter() - started) * 1000)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        if request.path.startswith('/api/'):
            # Decision context and impact evidence can contain private operational data.
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Pragma'] = 'no-cache'
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        db.session.rollback()
        # Database constraints are the final guard against concurrent duplicate/conflicting writes.
        # Return a generic message rather than exposing SQL or database details.
        app.logger.warning('Database integrity constraint rejected a write')
        return render_template('error.html', code=409,
                               message='The change conflicts with an existing record or another update happened at the same time. Refresh the page, review the current schedule, and try again.'), 409

    def require_roles(*roles):
        if not current_user.is_authenticated:
            abort(403)
        if current_user.role not in roles:
            abort(403)

    def record_audit(action, entity_type, entity_id=None, details=''):
        db.session.add(AuditEvent(user_id=current_user.id if current_user.is_authenticated else None,
                                  action=action, entity_type=entity_type, entity_id=entity_id,
                                  details=details[:500]))

    @app.get('/livez')
    def livez():
        # Liveness avoids dependency checks; /healthz remains the database readiness probe.
        return {'status': 'alive'}, 200

    @app.get('/healthz')
    def healthz():
        # Keep health checks minimal; never return connection strings or exception details.
        try:
            db.session.execute(text('SELECT 1'))
            return {'status': 'ok', 'database': 'reachable'}, 200
        except Exception:
            db.session.rollback()
            app.logger.exception('Health check database probe failed')
            return {'status': 'unavailable', 'database': 'unreachable'}, 503

    def json_error(message, status=400):
        return {'error': message}, status

    def validate_analysis_payload(payload, require_alternative=False):
        if not isinstance(payload, dict):
            return None, 'Send a JSON object.'
        domain = str(payload.get('domain', '')).strip()
        variable = str(payload.get('variable', '')).strip()
        current_value = str(payload.get('current_value', '')).strip()
        proposed_value = str(payload.get('proposed_value', '')).strip()
        context = str(payload.get('context', '')).strip()
        alternative_value = str(payload.get('alternative_value', '')).strip()
        if domain not in DOMAINS:
            return None, 'Choose a supported domain.'
        if variable not in VARIABLES:
            return None, 'Choose a supported change variable.'
        if not current_value or len(current_value) > 120:
            return None, 'current_value must contain 1–120 characters.'
        if not proposed_value or len(proposed_value) > 120:
            return None, 'proposed_value must contain 1–120 characters.'
        if len(context) > 1000:
            return None, 'context must be 1000 characters or fewer.'
        if require_alternative and (not alternative_value or len(alternative_value) > 120):
            return None, 'alternative_value must contain 1–120 characters.'
        return {
            'domain': domain, 'variable': variable, 'current_value': current_value,
            'proposed_value': proposed_value, 'context': context,
            'alternative_value': alternative_value,
        }, None

    def impact_summary(items):
        return {
            'total': len(items),
            'by_level': {str(level): sum(1 for item in items if item.get('level') == level)
                         for level in (1, 2, 3)},
            'by_severity': {severity: sum(1 for item in items if item.get('severity') == severity)
                            for severity in ('Critical', 'High', 'Medium', 'Low')},
            'mitigations_available': sum(1 for item in items if str(item.get('mitigation', '')).strip()),
        }

    @app.post('/api/v1/analyze')
    @login_required
    def api_analyze_change():
        """Authenticated, read-only API for proposed-change impact analysis."""
        payload, error = validate_analysis_payload(request.get_json(silent=True))
        if error:
            return json_error(error)
        evidence = collect_impact_evidence(payload['domain'], payload['variable'],
                                           payload['current_value'], payload['proposed_value'],
                                           payload['context'])
        impacts = analyze(payload['domain'], payload['variable'], payload['current_value'],
                          payload['proposed_value'], payload['context'], evidence)
        return {
            'analysis_version': RULE_VERSION,
            'status': 'analysis_complete',
            'change': {key: payload[key] for key in ('domain', 'variable', 'current_value', 'proposed_value', 'context')},
            'summary': impact_summary(impacts),
            'impacts': impacts,
            'evidence_count': len(evidence),
            'interpretation': 'Rule-based items are hypotheses, not verified facts. Database evidence only reflects records currently stored locally; confirm freshness and authority before acting.',
            'mutates_saved_scenarios': False,
        }, 200

    @app.post('/api/v1/compare')
    @login_required
    def api_compare_change():
        """Compare a proposed change with an alternative without saving either scenario."""
        from .evidence import compare_impacts
        payload, error = validate_analysis_payload(request.get_json(silent=True), require_alternative=True)
        if error:
            return json_error(error)
        def build(value):
            evidence = collect_impact_evidence(payload['domain'], payload['variable'],
                                               payload['current_value'], value, payload['context'])
            return analyze(payload['domain'], payload['variable'], payload['current_value'],
                           value, payload['context'], evidence)
        baseline = build(payload['proposed_value'])
        alternative = build(payload['alternative_value'])
        comparison = compare_impacts(baseline, alternative)
        high_before = sum(1 for item in baseline if item.get('severity') in ('High', 'Critical'))
        high_after = sum(1 for item in alternative if item.get('severity') in ('High', 'Critical'))
        if high_after < high_before:
            recommendation = 'The alternative has fewer high/critical-severity items under the current rules and stored evidence. Review feasibility and confirm the source records before choosing it.'
        elif high_after > high_before:
            recommendation = 'The alternative has more high/critical-severity items under the current rules and stored evidence. Review other alternatives or add a documented mitigation.'
        else:
            recommendation = 'The current analysis does not establish that either option is safer. Compare the remaining and new impacts, confirm the records, and ask the responsible owner to review.'
        return {
            'analysis_version': RULE_VERSION,
            'baseline_summary': impact_summary(baseline),
            'alternative_summary': impact_summary(alternative),
            'comparison': comparison,
            'recommendation': recommendation,
            'mutates_saved_scenarios': False,
            'interpretation': 'This comparison is a transparent heuristic, not a validated risk score or an approval decision.',
        }, 200

    def serialize_impact(item):
        return {
            'id': item.id, 'level': item.level, 'activity': item.activity,
            'description': item.description, 'cause': item.cause,
            'parent_activity': item.parent_activity, 'severity': item.severity,
            'likelihood': item.likelihood, 'mitigation': item.mitigation,
            'source': item.source, 'evidence_ref': item.evidence_ref,
        }

    def serialize_scenario(scenario, include_impacts=False):
        result = {
            'id': scenario.id, 'title': scenario.title, 'domain': scenario.domain,
            'change_variable': scenario.change_variable, 'current_value': scenario.current_value,
            'proposed_value': scenario.proposed_value, 'context': scenario.context,
            'status': scenario.status, 'approval_note': scenario.approval_note,
            'analysis_version': scenario.analysis_version,
            'analyzed_at': scenario.analyzed_at.isoformat() if scenario.analyzed_at else None,
            'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
            'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None,
            'impact_count': len(scenario.impacts),
        }
        if include_impacts:
            result['impacts'] = [serialize_impact(item) for item in scenario.impacts]
        return result

    @app.get('/api/v1/meta')
    @login_required
    def api_metadata():
        return {
            'api_version': 'v1', 'analysis_version': RULE_VERSION,
            'domains': list(DOMAINS), 'variables': list(VARIABLES),
            'authentication': 'authenticated browser session',
            'write_requests_require_csrf': True,
        }, 200

    @app.get('/api/v1/scenarios')
    @login_required
    def api_list_scenarios():
        """List only the current user's saved decisions with bounded pagination."""
        try:
            page = max(1, int(request.args.get('page', '1')))
            per_page = min(100, max(1, int(request.args.get('per_page', '20'))))
        except (TypeError, ValueError):
            return json_error('page and per_page must be integers.')
        query_text = request.args.get('q', '').strip()[:120]
        query = Scenario.query.filter_by(user_id=current_user.id)
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(or_(Scenario.title.ilike(pattern), Scenario.domain.ilike(pattern),
                                     Scenario.change_variable.ilike(pattern), Scenario.context.ilike(pattern)))
        pagination = query.order_by(Scenario.updated_at.desc(), Scenario.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
        return {
            'items': [serialize_scenario(item) for item in pagination.items],
            'pagination': {'page': pagination.page, 'per_page': pagination.per_page,
                           'total': pagination.total, 'pages': pagination.pages,
                           'has_next': pagination.has_next, 'has_prev': pagination.has_prev},
        }, 200

    @app.get('/api/v1/scenarios/<int:scenario_id>')
    @login_required
    def api_get_scenario(scenario_id):
        """Return a saved decision and its impact chain, respecting workspace privacy."""
        scenario = db.session.get(Scenario, scenario_id)
        if not scenario or (scenario.user_id != current_user.id and current_user.role not in ('coordinator', 'admin')):
            abort(404)
        return serialize_scenario(scenario, include_impacts=True), 200

    @app.route('/decisions/add-and-import', methods=['GET', 'POST'])
    @login_required
    def add_decision_and_import_csv():
        """Append a validated decision to the canonical CSV and import it atomically."""
        if request.method == 'GET':
            return render_template('scenario_form.html', scenario=None, append_to_csv=True)
        payload = {
            'title': request.form.get('decision_title', request.form.get('title', '')),
            'domain': request.form.get('domain', ''),
            'change_variable': request.form.get('change_variable', ''),
            'current_value': request.form.get('current_value', ''),
            'proposed_value': request.form.get('proposed_value', ''),
            'context': request.form.get('context', ''),
        }
        data, error = scenario_form_data(payload)
        if error:
            flash(error, 'error')
            return render_template('scenario_form.html', scenario=None, append_to_csv=True), 400

        # The lock prevents lost updates between simultaneous requests in this process.
        lock = app.extensions.setdefault('decision_csv_lock', threading.RLock())
        csv_path = Path(app.config.get('DECISIONS_CSV_PATH') or (Path(app.instance_path) / 'decisions.csv'))
        headers = ['title', 'domain', 'change_variable', 'current_value', 'proposed_value', 'context']
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with lock:
            original = csv_path.read_bytes() if csv_path.exists() else None
            try:
                existing_rows = []
                if original:
                    try:
                        reader = csv.DictReader(io.StringIO(original.decode('utf-8-sig', errors='strict'), newline=''))
                        if reader.fieldnames != headers:
                            raise ValueError('The decisions CSV has unexpected headers. Back it up and repair its schema before retrying.')
                        existing_rows = list(reader)
                    except (UnicodeDecodeError, csv.Error) as exc:
                        raise ValueError('The decisions CSV is malformed or is not UTF-8 encoded.') from exc
                # Retry-safe idempotency: an exact duplicate row is not appended again.
                if any(all((row.get(k) or '') == str(data[k]) for k in headers) for row in existing_rows):
                    existing = Scenario.query.filter_by(user_id=current_user.id, title=data['title'], domain=data['domain'],
                        change_variable=data['change_variable'], current_value=data['current_value'],
                        proposed_value=data['proposed_value'], context=data['context']).first()
                    if existing:
                        flash('This decision already exists; no duplicate CSV row was added.', 'success')
                        return redirect(url_for('scenario_detail', scenario_id=existing.id))
                    raise ValueError('This decision row is already in the CSV. Import it from the existing CSV rather than adding a duplicate.')
                output = io.StringIO(newline='')
                writer = csv.writer(output, lineterminator='\n')
                if not original:
                    writer.writerow(headers)
                writer.writerow([data[k] for k in headers])
                encoded = output.getvalue().encode('utf-8')
                # Write the complete new file to a temporary sibling, then atomically replace.
                previous_text = original.decode('utf-8-sig') if original else ''
                prefix = previous_text
                if prefix and not prefix.endswith(('\n', '\r')):
                    prefix += '\n'
                complete = (prefix.encode('utf-8') + encoded) if original else encoded
                fd, temp_name = tempfile.mkstemp(prefix='.decisions-', suffix='.csv.tmp', dir=str(csv_path.parent))
                try:
                    with os.fdopen(fd, 'wb') as temp_file:
                        temp_file.write(complete)
                        temp_file.flush()
                        os.fsync(temp_file.fileno())
                    os.replace(temp_name, csv_path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)

                # Reuse the same validated payload/schema as the CSV import endpoint.
                scenario = Scenario(user_id=current_user.id, **data)
                db.session.add(scenario)
                db.session.flush()
                record_audit('scenario.csv_appended_and_imported', 'Scenario', scenario.id,
                             details=f'Canonical CSV updated: {csv_path.name}')
                db.session.commit()
                flash('Decision saved to CSV and imported successfully. You can now analyze its impacts.', 'success')
                return redirect(url_for('scenario_detail', scenario_id=scenario.id))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), 'error')
                return render_template('scenario_form.html', scenario=None, append_to_csv=True), 400
            except (OSError, PermissionError, csv.Error, UnicodeError) as exc:
                db.session.rollback()
                app.logger.exception('Decision CSV update failed')
                flash('Could not update the decisions CSV. Check file permissions and encoding, then retry.', 'error')
                return render_template('scenario_form.html', scenario=None, append_to_csv=True), 500
            except Exception:
                db.session.rollback()
                # If DB import fails, restore the original CSV to keep both stores consistent.
                try:
                    if original is None:
                        csv_path.unlink(missing_ok=True)
                    else:
                        restore_fd, restore_name = tempfile.mkstemp(prefix='.decisions-restore-', dir=str(csv_path.parent))
                        with os.fdopen(restore_fd, 'wb') as restore_file:
                            restore_file.write(original)
                            restore_file.flush()
                            os.fsync(restore_file.fileno())
                        os.replace(restore_name, csv_path)
                except OSError:
                    app.logger.exception('CSV rollback failed; manual recovery is required for %s', csv_path)
                app.logger.exception('Decision CSV import failed')
                flash('The decision could not be imported. The CSV was restored where possible; retry safely.', 'error')
                return render_template('scenario_form.html', scenario=None, append_to_csv=True), 500

    @app.route('/imports', methods=['GET', 'POST'])
    @login_required
    def import_scenarios():
        if request.method == 'POST':
            upload = request.files.get('file')
            if not upload or not upload.filename or not upload.filename.lower().endswith('.csv'):
                flash('Choose a CSV file to import.', 'error')
                return redirect(url_for('import_scenarios'))
            raw = upload.stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                flash('CSV must be 1 MB or smaller.', 'error')
                return redirect(url_for('import_scenarios'))
            try:
                reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
                required = {'title', 'domain', 'change_variable', 'current_value', 'proposed_value', 'context'}
                if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                    flash('CSV needs columns: title, domain, change_variable, current_value, proposed_value, context.', 'error')
                    return redirect(url_for('import_scenarios'))
                rows = list(reader)
            except (UnicodeDecodeError, csv.Error):
                flash('Could not read this CSV. Save it as CSV UTF-8 and try again.', 'error')
                return redirect(url_for('import_scenarios'))
            if not rows or len(rows) > 200:
                flash('Import between 1 and 200 decision rows at a time.', 'error')
                return redirect(url_for('import_scenarios'))
            validated = []
            errors = []
            for row_number, row in enumerate(rows, start=2):
                data, error = scenario_form_data(row)
                if error:
                    errors.append(f'Row {row_number}: {error}')
                else:
                    validated.append(data)
            if errors:
                for message in errors[:8]:
                    flash(message, 'error')
                if len(errors) > 8:
                    flash(f'{len(errors) - 8} more row errors were found.', 'error')
            else:
                for data in validated:
                    db.session.add(Scenario(user_id=current_user.id, **data))
                record_audit('scenario.csv_imported', 'Scenario', details=f'{len(validated)} scenarios imported')
                db.session.commit()
                flash(f'Imported {len(validated)} college decision scenarios as drafts.', 'success')
                return redirect(url_for('dashboard'))
        return render_template('imports.html')

    @app.get('/imports/template.csv')
    @login_required
    def import_template():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['title', 'domain', 'change_variable', 'current_value', 'proposed_value', 'context'])
        writer.writerow(['Move lab session', 'Timetable & classrooms', 'Time', '10:00', '12:00', 'Verify room and faculty availability'])
        response = make_response('\ufeff' + output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="campusripple-import-template.csv"'
        return response

    @app.get('/admin/users')
    @login_required
    def admin_users():
        require_roles('admin')
        query_text = request.args.get('q', '').strip()[:100]
        query = User.query
        if query_text:
            pattern = f'%{query_text}%'
            query = query.filter(or_(User.name.ilike(pattern), User.email.ilike(pattern), User.role.ilike(pattern)))
        page = max(1, request.args.get('page', 1, type=int) or 1)
        per_page = 25
        total_users = query.count()
        pages = max(1, (total_users + per_page - 1) // per_page)
        page = min(page, pages)
        users = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return render_template('admin_users.html', users=users, q=query_text, page=page, pages=pages, total_users=total_users)

    @app.route('/admin/integrations', methods=['GET', 'POST'])
    @login_required
    def admin_integrations():
        require_roles('admin')
        if request.method == 'POST':
            from .integrations.sync import sync_official_timetable
            try:
                result = sync_official_timetable(app)
                record_audit('integration.timetable_sync_succeeded', 'IntegrationSyncRun', details=str(result))
                db.session.commit()
                flash(f"Official timetable sync completed: {result['received']} received, {result['created']} created, {result['updated']} updated.", 'success')
            except Exception as exc:
                db.session.rollback()
                app.logger.warning('Official timetable sync failed: %s', type(exc).__name__)
                record_audit('integration.timetable_sync_failed', 'IntegrationSyncRun', details=type(exc).__name__)
                db.session.commit()
                flash('Timetable sync failed. Review the recent sync record and server logs; no partial timetable changes were committed.', 'error')
            return redirect(url_for('admin_integrations'))
        runs = IntegrationSyncRun.query.order_by(IntegrationSyncRun.started_at.desc()).limit(25).all()
        configured = bool(app.config.get('COLLEGE_DATA_API_URL') and app.config.get('COLLEGE_DATA_API_TOKEN'))
        return render_template('admin_integrations.html', runs=runs, configured=configured)

    @app.post('/admin/users/<int:user_id>/role')
    @login_required
    def admin_set_role(user_id):
        require_roles('admin')
        user = db.session.get(User, user_id)
        role = request.form.get('role', '')
        if not user or role not in ('student', 'faculty', 'coordinator', 'admin'):
            abort(404)
        if not is_eligible_college_email(user.email):
            flash('This account is not eligible for ACE Engineering College access. Remove or disable it through the approved account-cleanup process.', 'error')
            return redirect(url_for('admin_users'))
        if user.id == current_user.id and role != 'admin':
            flash('You cannot remove your own administrator role.', 'error')
        else:
            old_role = user.role
            user.role = role
            record_audit('user.role_changed', 'User', user.id, f'{old_role} → {role}')
            db.session.commit()
            flash('User role updated.', 'success')
        return redirect(url_for('admin_users'))

    @app.post('/scenarios/<int:scenario_id>/approval')
    @login_required
    def scenario_approval(scenario_id):
        require_roles('coordinator', 'admin')
        scenario = db.session.get(Scenario, scenario_id)
        if not scenario:
            abort(404)
        action = request.form.get('action', '')
        note = request.form.get('approval_note', '').strip()
        if len(note) > 1000:
            flash('Review note must be 1,000 characters or fewer.', 'error')
        elif action not in ('submit', 'approve', 'reject'):
            flash('Choose a valid review action.', 'error')
        else:
            scenario.status = {'submit': 'Pending review', 'approve': 'Approved', 'reject': 'Rejected'}[action]
            scenario.approval_note = note
            record_audit(f'scenario.{action}', 'Scenario', scenario.id, note or scenario.status)
            db.session.commit()
            flash(f'Decision marked {scenario.status.lower()}.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id))

    @app.get('/college-workspace')
    @login_required
    def college_workspace():
        departments = Department.query.order_by(Department.code).all()
        courses = Course.query.order_by(Course.code).all()
        rooms = Room.query.order_by(Room.code).all()
        entries = TimetableEntry.query.order_by(TimetableEntry.day_of_week, TimetableEntry.start_time).all()
        return render_template('college_workspace.html', departments=departments, courses=courses,
                               rooms=rooms, entries=entries, can_manage=current_user.role in ('coordinator', 'admin'))

    @app.post('/college-workspace/departments')
    @login_required
    def add_department():
        require_roles('coordinator', 'admin')
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        if not code or len(code) > 16 or not name or len(name) > 120:
            flash('Enter a department code and name within the allowed length.', 'error')
        elif Department.query.filter(or_(Department.code == code, Department.name == name)).first():
            flash('A department with that code or name already exists.', 'error')
        else:
            item = Department(code=code, name=name)
            db.session.add(item)
            record_audit('department.created', 'Department', details=f'{code} — {name}')
            db.session.commit()
            flash('Department added.', 'success')
        return redirect(url_for('college_workspace'))

    @app.post('/college-workspace/courses')
    @login_required
    def add_course():
        require_roles('coordinator', 'admin')
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        year = request.form.get('academic_year', '').strip()
        semester = request.form.get('semester', '').strip()
        department_id = request.form.get('department_id', type=int)
        department = db.session.get(Department, department_id) if department_id else None
        if not code or len(code) > 24 or not name or len(name) > 120 or not year or len(year) > 20 or not semester or len(semester) > 20 or not department:
            flash('Complete every course field and choose a valid department.', 'error')
        elif Course.query.filter_by(code=code).first():
            flash('That course code already exists.', 'error')
        else:
            db.session.add(Course(code=code, name=name, department_id=department.id, academic_year=year, semester=semester))
            record_audit('course.created', 'Course', details=f'{code} — {name}')
            db.session.commit()
            flash('Course added.', 'success')
        return redirect(url_for('college_workspace'))

    @app.post('/college-workspace/rooms')
    @login_required
    def add_room():
        require_roles('coordinator', 'admin')
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        room_type = request.form.get('room_type', 'Classroom').strip()
        capacity = request.form.get('capacity', type=int)
        if not code or len(code) > 24 or not name or len(name) > 120 or room_type not in ('Classroom', 'Lab', 'Hall', 'Other') or capacity is None or capacity < 0 or capacity > 10000:
            flash('Enter a valid room name, type, and capacity (0–10,000).', 'error')
        elif Room.query.filter_by(code=code).first():
            flash('That room code already exists.', 'error')
        else:
            db.session.add(Room(code=code, name=name, room_type=room_type, capacity=capacity))
            record_audit('room.created', 'Room', details=f'{code} — {name}')
            db.session.commit()
            flash('Room or lab added.', 'success')
        return redirect(url_for('college_workspace'))

    @app.post('/college-workspace/timetable')
    @login_required
    def add_timetable_entry():
        require_roles('coordinator', 'admin')
        course_id = request.form.get('course_id', type=int)
        room_id = request.form.get('room_id', type=int)
        faculty = request.form.get('faculty_name', '').strip()
        day = request.form.get('day_of_week', '')
        start = request.form.get('start_time', '')
        end = request.form.get('end_time', '')
        subject = request.form.get('subject', '').strip()
        course = db.session.get(Course, course_id) if course_id else None
        room = db.session.get(Room, room_id) if room_id else None
        days = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        valid_time = lambda value: len(value) == 5 and value[2] == ':' and value[:2].isdigit() and value[3:].isdigit() and 0 <= int(value[:2]) <= 23 and 0 <= int(value[3:]) <= 59
        if not course or not room or not faculty or len(faculty) > 100 or day not in days or not valid_time(start) or not valid_time(end) or start >= end or not subject or len(subject) > 120:
            flash('Complete all timetable fields with valid times; end time must follow start time.', 'error')
            return redirect(url_for('college_workspace'))
        # PostgreSQL transaction-scoped advisory lock serializes timetable writes for a day.
        # This closes the check-then-insert race between concurrent web workers.
        if db.engine.dialect.name == 'postgresql':
            db.session.execute(text('SELECT pg_advisory_xact_lock(hashtext(:lock_key))'),
                               {'lock_key': f'campusripple:timetable:{day}'})
        conflicts = TimetableEntry.query.filter(TimetableEntry.day_of_week == day,
            TimetableEntry.start_time < end, TimetableEntry.end_time > start).all()
        for existing in conflicts:
            if existing.room_id == room.id:
                flash(f'Room conflict: {room.code} is already booked for {existing.start_time}–{existing.end_time}.', 'error')
                return redirect(url_for('college_workspace'))
            if existing.faculty_name.casefold() == faculty.casefold():
                flash(f'Faculty conflict: {faculty} already has a session at that time.', 'error')
                return redirect(url_for('college_workspace'))
            if existing.course_id == course.id:
                flash(f'Course conflict: {course.code} already has a session at that time.', 'error')
                return redirect(url_for('college_workspace'))
        db.session.add(TimetableEntry(course_id=course.id, room_id=room.id, faculty_name=faculty, day_of_week=day,
                                      start_time=start, end_time=end, subject=subject))
        record_audit('timetable.created', 'TimetableEntry', details=f'{course.code}, {room.code}, {day} {start}-{end}')
        db.session.commit()
        flash('Timetable entry saved without a room or faculty overlap.', 'success')
        return redirect(url_for('college_workspace'))

    @app.post('/college-workspace/import-timetable')
    @login_required
    def import_official_timetable():
        require_roles('coordinator', 'admin')
        upload = request.files.get('file')
        if not upload or not upload.filename or not upload.filename.lower().endswith('.csv'):
            flash('Choose the official timetable as a UTF-8 CSV file.', 'error')
            return redirect(url_for('college_workspace'))
        raw = upload.stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            flash('Timetable import must be 1 MB or smaller.', 'error')
            return redirect(url_for('college_workspace'))
        try:
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            required = {'course_code', 'room_code', 'faculty_name', 'day_of_week', 'start_time', 'end_time', 'subject'}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError('Required columns: course_code, room_code, faculty_name, day_of_week, start_time, end_time, subject.')
            rows = list(reader)
            if not rows or len(rows) > 500:
                raise ValueError('Import between 1 and 500 timetable rows at a time.')
            staged, errors = [], []
            for row_no, row in enumerate(rows, 2):
                course_code = (row.get('course_code') or '').strip().upper()
                room_code = (row.get('room_code') or '').strip().upper()
                faculty = (row.get('faculty_name') or '').strip()
                day = (row.get('day_of_week') or '').strip().title()
                start = (row.get('start_time') or '').strip()
                end = (row.get('end_time') or '').strip()
                subject = (row.get('subject') or '').strip()
                course = Course.query.filter_by(code=course_code).first()
                room = Room.query.filter_by(code=room_code, is_active=True).first()
                if not course or not room or not faculty or len(faculty) > 100 or day not in ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday') or not valid_clock(start) or not valid_clock(end) or start >= end or not subject or len(subject) > 120:
                    errors.append(f'Row {row_no}: invalid or unknown course/room/faculty/day/time/subject.')
                    continue
                clash = TimetableEntry.query.filter(TimetableEntry.day_of_week == day, TimetableEntry.start_time < end, TimetableEntry.end_time > start).filter((TimetableEntry.room_id == room.id) | (func.lower(TimetableEntry.faculty_name) == faculty.lower()) | (TimetableEntry.course_id == course.id)).first()
                staged_clash = next((item for item in staged if item['day_of_week'] == day and item['start_time'] < end and item['end_time'] > start and (item['room_id'] == room.id or item['faculty_name'].casefold() == faculty.casefold() or item['course_id'] == course.id)), None)
                if clash or staged_clash:
                    errors.append(f'Row {row_no}: conflicts with an existing or imported timetable entry.')
                    continue
                staged.append({'course_id': course.id, 'room_id': room.id, 'faculty_name': faculty, 'day_of_week': day, 'start_time': start, 'end_time': end, 'subject': subject})
            if errors:
                for message in errors[:10]: flash(message, 'error')
                if len(errors) > 10: flash(f'{len(errors)-10} more errors found; nothing was imported.', 'error')
                return redirect(url_for('college_workspace'))
            if db.engine.dialect.name == 'postgresql':
                for day in sorted({item['day_of_week'] for item in staged}):
                    db.session.execute(text('SELECT pg_advisory_xact_lock(hashtext(:lock_key))'), {'lock_key': f'campusripple:timetable:{day}'})
            for item in staged:
                item['source_system'] = 'official_csv'
                item['source_synced_at'] = datetime.now(timezone.utc)
                db.session.add(TimetableEntry(**item))
            record_audit('timetable.official_csv_imported', 'TimetableEntry', details=f'{len(staged)} rows; file={upload.filename[:100]}')
            db.session.commit()
            flash(f'Imported {len(staged)} validated timetable rows. Verify them against the official college source.', 'success')
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            db.session.rollback()
            flash(str(exc)[:300] or 'Could not parse timetable CSV.', 'error')
        return redirect(url_for('college_workspace'))

    @app.route('/college-operations', methods=['GET', 'POST'])
    @login_required
    def college_operations():
        can_manage = current_user.role in ('coordinator', 'admin')
        if request.method == 'POST':
            require_roles('coordinator', 'admin')
            kind = request.form.get('kind', '')
            try:
                if kind == 'exam':
                    title = request.form.get('title', '').strip()
                    exam_date = request.form.get('event_date', '').strip()
                    start = request.form.get('start_time', '').strip()
                    end = request.form.get('end_time', '').strip()
                    course = db.session.get(Course, request.form.get('course_id', type=int))
                    room = db.session.get(Room, request.form.get('room_id', type=int))
                    if not title or len(title) > 140 or not valid_iso_date(exam_date) or not valid_clock(start) or not valid_clock(end) or start >= end or not course or not room or not room.is_active:
                        raise ValueError('Complete the exam fields with a valid date, time, course and active room.')
                    clash = ExamSchedule.query.filter_by(exam_date=exam_date, room_id=room.id).filter(ExamSchedule.start_time < end, ExamSchedule.end_time > start).first()
                    if clash:
                        raise ValueError(f'Exam hall conflict: {room.code} is already booked for {clash.start_time}–{clash.end_time}.')
                    db.session.add(ExamSchedule(title=title, exam_date=exam_date, start_time=start, end_time=end, course_id=course.id, room_id=room.id, created_by=current_user.id))
                    record_audit('exam.created', 'ExamSchedule', details=f'{title}; {exam_date}; {room.code}')
                    db.session.commit()
                    flash('Exam schedule added.', 'success')
                elif kind == 'event':
                    title = request.form.get('title', '').strip()
                    event_date = request.form.get('event_date', '').strip()
                    location = request.form.get('location', '').strip()
                    organizer = request.form.get('organizer', '').strip()
                    details = request.form.get('details', '').strip()
                    if not title or len(title) > 140 or not valid_iso_date(event_date) or not location or len(location) > 140 or not organizer or len(organizer) > 100 or len(details) > 1000:
                        raise ValueError('Enter a valid event title, date, location and organizer.')
                    db.session.add(CampusEvent(title=title, event_date=event_date, location=location, organizer=organizer, details=details, created_by=current_user.id))
                    record_audit('event.created', 'CampusEvent', details=f'{title}; {event_date}; {location}')
                    db.session.commit()
                    flash('Campus event added.', 'success')
                elif kind == 'maintenance':
                    room = db.session.get(Room, request.form.get('room_id', type=int))
                    title = request.form.get('title', '').strip()
                    description = request.form.get('details', '').strip()
                    priority = request.form.get('priority', 'Medium')
                    if not room or not title or len(title) > 140 or not description or len(description) > 2000 or priority not in ('Low', 'Medium', 'High', 'Urgent'):
                        raise ValueError('Enter a valid room, issue, description and priority.')
                    db.session.add(MaintenanceRequest(room_id=room.id, title=title, description=description, priority=priority, reported_by=current_user.id))
                    record_audit('maintenance.created', 'MaintenanceRequest', details=f'{priority}; {room.code}; {title}')
                    db.session.commit()
                    flash('Maintenance request submitted.', 'success')
                else:
                    raise ValueError('Choose a valid operation type.')
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), 'error')
            except Exception:
                db.session.rollback()
                app.logger.exception('College operation could not be saved')
                flash('The record could not be saved. Check for duplicate or invalid data and try again.', 'error')
            return redirect(url_for('college_operations'))
        exams = ExamSchedule.query.order_by(ExamSchedule.exam_date, ExamSchedule.start_time).limit(300).all()
        events = CampusEvent.query.order_by(CampusEvent.event_date).limit(300).all()
        maintenance = MaintenanceRequest.query.order_by(MaintenanceRequest.created_at.desc()).limit(300).all()
        courses = Course.query.order_by(Course.code).all()
        rooms = Room.query.filter_by(is_active=True).order_by(Room.code).all()
        return render_template('college_operations.html', can_manage=can_manage, exams=exams, events=events,
                               maintenance=maintenance, courses=courses, rooms=rooms)

    @app.post('/campus-services/attendance/<int:record_id>/verify')
    @login_required
    def verify_attendance(record_id):
        require_roles('faculty', 'coordinator', 'admin')
        record = db.session.get(AttendanceRecord, record_id)
        decision = request.form.get('decision', '')
        if not record or decision not in ('Present', 'Absent', 'Rejected'):
            abort(404)
        record.status = decision
        record.verified_by = current_user.id
        record.verified_at = datetime.now(timezone.utc)
        record_audit('attendance.staff_verified', 'AttendanceRecord', record.id,
                     f'status={decision}; session={record.session_id}; student={record.user_id}')
        db.session.commit()
        flash(f'Attendance record marked {decision.lower()} by staff.', 'success')
        return redirect(url_for('campus_services'))

    @app.post('/college-operations/maintenance/<int:request_id>/status')
    @login_required
    def update_maintenance_status(request_id):
        require_roles('coordinator', 'admin')
        item = db.session.get(MaintenanceRequest, request_id)
        status = request.form.get('status', '')
        if not item or status not in ('Open', 'In progress', 'Resolved', 'Cancelled'):
            abort(404)
        item.status = status
        record_audit('maintenance.status_changed', 'MaintenanceRequest', item.id, status)
        db.session.commit()
        flash('Maintenance status updated.', 'success')
        return redirect(url_for('college_operations'))

    @app.route('/campus-services', methods=['GET', 'POST'])
    @login_required
    def campus_services():
        can_manage = current_user.role in ('faculty', 'coordinator', 'admin')
        if request.method == 'POST':
            kind = request.form.get('kind', '')
            try:
                if kind == 'attendance_session':
                    require_roles('faculty', 'coordinator', 'admin')
                    title = request.form.get('title', '').strip()
                    date = request.form.get('session_date', '').strip()
                    start = request.form.get('start_time', '').strip()
                    end = request.form.get('end_time', '').strip()
                    course_id = request.form.get('course_id', type=int)
                    course = db.session.get(Course, course_id) if course_id else None
                    if not title or len(title) > 140 or not valid_iso_date(date) or not valid_clock(start) or not valid_clock(end) or start >= end:
                        raise ValueError('Enter a valid attendance title, date and time range.')
                    if course_id and not course:
                        raise ValueError('Select a valid course.')
                    item = AttendanceSession(title=title, course_id=course.id if course else None, session_date=date,
                                             start_time=start, end_time=end, created_by=current_user.id)
                    db.session.add(item)
                    db.session.flush()
                    record_audit('attendance.session_created', 'AttendanceSession', item.id, title)
                    db.session.commit()
                    flash('Attendance session created. Students can check in once; verify identity through college procedures.', 'success')
                elif kind == 'attendance_checkin':
                    session_id = request.form.get('session_id', type=int)
                    item = db.session.get(AttendanceSession, session_id) if session_id else None
                    if not item or item.status != 'Open':
                        raise ValueError('This attendance session is not open.')
                    exists = AttendanceRecord.query.filter_by(session_id=item.id, user_id=current_user.id).first()
                    if exists:
                        raise ValueError('You have already checked in to this session.')
                    record = AttendanceRecord(session_id=item.id, user_id=current_user.id, status='Unverified')
                    db.session.add(record)
                    record_audit('attendance.checked_in', 'AttendanceRecord', details=f'session={item.id}')
                    db.session.commit()
                    flash('Check-in recorded as unverified. It becomes official only after faculty/coordinator verification.', 'success')
                elif kind == 'attendance_status':
                    require_roles('faculty', 'coordinator', 'admin')
                    item = db.session.get(AttendanceSession, request.form.get('session_id', type=int))
                    status = request.form.get('status', '')
                    if not item or status not in ('Open', 'Closed'):
                        raise ValueError('Select a valid attendance session and status.')
                    item.status = status
                    record_audit('attendance.session_status', 'AttendanceSession', item.id, status)
                    db.session.commit()
                    flash('Attendance session updated.', 'success')
                elif kind == 'inventory':
                    require_roles('coordinator', 'admin')
                    code = request.form.get('item_code', '').strip().upper()
                    name = request.form.get('name', '').strip()
                    category = request.form.get('category', 'General').strip()
                    location = request.form.get('location', '').strip()
                    quantity = request.form.get('quantity', type=int)
                    reorder = request.form.get('reorder_level', type=int)
                    if not code or len(code) > 32 or not name or len(name) > 140 or not category or len(category) > 60 or not location or len(location) > 120 or quantity is None or reorder is None or quantity < 0 or reorder < 0 or quantity > 10000000 or reorder > 10000000:
                        raise ValueError('Complete inventory fields with valid non-negative quantities.')
                    if InventoryItem.query.filter_by(item_code=code).first():
                        raise ValueError('That inventory code already exists.')
                    item = InventoryItem(item_code=code, name=name, category=category, location=location, quantity=quantity, reorder_level=reorder)
                    db.session.add(item)
                    db.session.flush()
                    record_audit('inventory.created', 'InventoryItem', item.id, f'{code}: quantity={quantity}')
                    db.session.commit()
                    flash('Inventory item added.', 'success')
                elif kind == 'inventory_adjust':
                    require_roles('coordinator', 'admin')
                    item = db.session.get(InventoryItem, request.form.get('item_id', type=int))
                    delta = request.form.get('delta', type=int)
                    note = request.form.get('note', '').strip()
                    if not item or delta is None or delta == 0 or abs(delta) > 1000000 or item.quantity + delta < 0 or len(note) > 200:
                        raise ValueError('Enter a valid stock adjustment; quantity cannot become negative.')
                    item.quantity += delta
                    record_audit('inventory.adjusted', 'InventoryItem', item.id, f'delta={delta}; {note}')
                    db.session.commit()
                    flash('Inventory quantity updated.', 'success')
                elif kind == 'announcement':
                    require_roles('coordinator', 'admin')
                    title = request.form.get('title', '').strip()
                    body = request.form.get('body', '').strip()
                    audience = request.form.get('audience', 'All')
                    expiry = request.form.get('expires_on', '').strip() or None
                    if not title or len(title) > 140 or not body or len(body) > 3000 or audience not in ('All', 'Students', 'Faculty') or (expiry and not valid_iso_date(expiry)):
                        raise ValueError('Enter a valid announcement title, message, audience and optional expiry date.')
                    item = Announcement(title=title, body=body, audience=audience, expires_on=expiry, created_by=current_user.id)
                    db.session.add(item)
                    db.session.flush()
                    record_audit('announcement.published', 'Announcement', item.id, f'{title}; audience={audience}')
                    db.session.commit()
                    flash('Announcement published.', 'success')
                else:
                    raise ValueError('Choose a valid campus service action.')
            except HTTPException:
                db.session.rollback()
                raise
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), 'error')
            except Exception:
                db.session.rollback()
                app.logger.exception('Campus service action failed')
                flash('Could not save this change. Check the values and try again.', 'error')
            return redirect(url_for('campus_services'))

        today = datetime.now().date().isoformat()
        sessions = AttendanceSession.query.order_by(AttendanceSession.session_date.desc(), AttendanceSession.start_time).limit(100).all()
        records = AttendanceRecord.query.filter_by(user_id=current_user.id).all()
        checked_in = {r.session_id for r in records}
        inventory = InventoryItem.query.order_by(InventoryItem.name).limit(300).all()
        announcement_query = Announcement.query.filter_by(published=True)
        if current_user.role == 'student':
            announcement_query = announcement_query.filter(Announcement.audience.in_(('All', 'Students')))
        elif current_user.role == 'faculty':
            announcement_query = announcement_query.filter(Announcement.audience.in_(('All', 'Faculty')))
        announcements = announcement_query.filter(or_(Announcement.expires_on.is_(None), Announcement.expires_on >= today)).order_by(Announcement.created_at.desc()).limit(100).all()
        courses = Course.query.order_by(Course.code).all()
        attendance_records = AttendanceRecord.query.join(AttendanceSession).order_by(AttendanceRecord.marked_at.desc()).limit(500).all()
        return render_template('campus_services.html', can_manage=can_manage, sessions=sessions, checked_in=checked_in,
                               inventory=inventory, announcements=announcements, courses=courses, today=today, attendance_records=attendance_records)

    @app.route('/academic-services', methods=['GET', 'POST'])
    @login_required
    def academic_services():
        staff_roles = ('faculty', 'coordinator', 'admin')
        managers = ('coordinator', 'admin')
        if request.method == 'POST':
            kind = request.form.get('kind', '')
            if kind == 'service_request':
                title = request.form.get('title', '').strip()
                description = request.form.get('description', '').strip()
                category = request.form.get('category', 'General')
                priority = request.form.get('priority', 'Medium')
                if not title or len(title) > 140 or not description or len(description) > 3000 or category not in ('Academic', 'Facilities', 'IT', 'Safety', 'General') or priority not in ('Low', 'Medium', 'High', 'Urgent'):
                    flash('Complete the request fields with valid values.', 'error')
                else:
                    item = ServiceRequest(requester_id=current_user.id, title=title, description=description, category=category, priority=priority)
                    db.session.add(item)
                    db.session.flush()
                    for staff in User.query.filter(User.role.in_(managers)).all():
                        db.session.add(InAppNotification(user_id=staff.id, title='New campus service request', message=f'{category}: {title}', category='Service request'))
                    record_audit('service_request.created', 'ServiceRequest', item.id, title)
                    db.session.commit()
                    flash('Request submitted and routed to the administration queue.', 'success')
                return redirect(url_for('academic_services'))
            if kind == 'service_status':
                require_roles(*managers)
                item = db.session.get(ServiceRequest, request.form.get('request_id', type=int))
                status = request.form.get('status', '')
                note = request.form.get('resolution_note', '').strip()
                assignee_id = request.form.get('assigned_to', type=int)
                if not item or status not in ('Open', 'In progress', 'Waiting for student', 'Resolved', 'Rejected') or len(note) > 2000:
                    flash('Invalid request update.', 'error')
                else:
                    assignee = db.session.get(User, assignee_id) if assignee_id else None
                    if assignee and assignee.role not in staff_roles and assignee.role not in managers:
                        flash('Requests can only be assigned to college staff.', 'error')
                        return redirect(url_for('academic_services'))
                    item.status, item.resolution_note, item.assigned_to = status, note, assignee.id if assignee else None
                    db.session.add(InAppNotification(user_id=item.requester_id, title='Service request updated', message=f'{item.title}: {status}. {note}'[:1000], category='Service request'))
                    record_audit('service_request.updated', 'ServiceRequest', item.id, status)
                    db.session.commit()
                    flash('Service request updated.', 'success')
                return redirect(url_for('academic_services'))
            if kind == 'calendar_item':
                require_roles(*managers)
                title = request.form.get('title', '').strip()
                item_type = request.form.get('item_type', 'Deadline')
                start_date = request.form.get('start_date', '')
                end_date = request.form.get('end_date', '') or None
                audience = request.form.get('audience', 'All')
                details = request.form.get('details', '').strip()
                if not title or len(title) > 140 or not valid_iso_date(start_date) or (end_date and (not valid_iso_date(end_date) or end_date < start_date)) or item_type not in ('Holiday', 'Deadline', 'Academic', 'Exam', 'Event') or audience not in ('All', 'Students', 'Faculty') or len(details) > 2000:
                    flash('Enter a valid academic calendar item.', 'error')
                else:
                    item = AcademicCalendarItem(title=title, item_type=item_type, start_date=start_date, end_date=end_date, audience=audience, details=details, created_by=current_user.id)
                    db.session.add(item)
                    db.session.flush()
                    recipients = User.query.all()
                    for recipient in recipients:
                        if audience == 'All' or (audience == 'Students' and recipient.role == 'student') or (audience == 'Faculty' and recipient.role == 'faculty'):
                            db.session.add(InAppNotification(user_id=recipient.id, title=f'Academic calendar: {title}', message=f'{start_date}: {details or item_type}', category='Calendar'))
                    record_audit('calendar_item.created', 'AcademicCalendarItem', item.id, title)
                    db.session.commit()
                    flash('Academic calendar item published.', 'success')
                return redirect(url_for('academic_services'))
            if kind == 'substitution':
                require_roles(*staff_roles)
                entry = db.session.get(TimetableEntry, request.form.get('timetable_entry_id', type=int))
                substitute = db.session.get(User, request.form.get('substitute_user_id', type=int))
                reason = request.form.get('reason', '').strip()
                if not entry or not substitute or substitute.role != 'faculty' or not reason or len(reason) > 1000:
                    flash('Choose a timetable session and faculty substitute, and provide a reason.', 'error')
                elif substitute.name.casefold() == entry.faculty_name.casefold():
                    flash('Choose a different faculty member.', 'error')
                else:
                    clash = TimetableEntry.query.filter(TimetableEntry.day_of_week == entry.day_of_week, TimetableEntry.start_time < entry.end_time, TimetableEntry.end_time > entry.start_time, func.lower(TimetableEntry.faculty_name) == substitute.name.lower()).first()
                    existing = FacultySubstitution.query.join(TimetableEntry).filter(FacultySubstitution.status.in_(('Pending', 'Approved')), TimetableEntry.day_of_week == entry.day_of_week, TimetableEntry.start_time < entry.end_time, TimetableEntry.end_time > entry.start_time, FacultySubstitution.substitute_user_id == substitute.id).first()
                    if clash or existing:
                        flash('That faculty member already has an overlapping class or approved/pending substitution.', 'error')
                    else:
                        item = FacultySubstitution(timetable_entry_id=entry.id, substitute_user_id=substitute.id, reason=reason, requested_by=current_user.id)
                        db.session.add(item)
                        db.session.flush()
                        for manager in User.query.filter(User.role.in_(managers)).all():
                            db.session.add(InAppNotification(user_id=manager.id, title='Faculty substitution needs review', message=f'{entry.subject}: proposed substitute {substitute.name}', category='Substitution'))
                        record_audit('faculty_substitution.requested', 'FacultySubstitution', item.id, reason)
                        db.session.commit()
                        flash('Substitution request sent for coordinator review. The official timetable has not been changed.', 'success')
                return redirect(url_for('academic_services'))
            if kind == 'substitution_review':
                require_roles(*managers)
                item = db.session.get(FacultySubstitution, request.form.get('substitution_id', type=int))
                action = request.form.get('action', '')
                note = request.form.get('review_note', '').strip()
                if not item or action not in ('Approved', 'Rejected') or len(note) > 1000:
                    flash('Invalid substitution review.', 'error')
                elif action == 'Approved':
                    entry = item.timetable_entry
                    clash = TimetableEntry.query.filter(TimetableEntry.id != entry.id, TimetableEntry.day_of_week == entry.day_of_week, TimetableEntry.start_time < entry.end_time, TimetableEntry.end_time > entry.start_time, func.lower(TimetableEntry.faculty_name) == item.substitute.name.lower()).first()
                    if clash:
                        flash('Cannot approve: substitute now has a timetable clash.', 'error')
                        return redirect(url_for('academic_services'))
                    item.status = 'Approved'
                    item.reviewed_by = current_user.id
                    item.review_note = note
                    db.session.add(InAppNotification(user_id=item.requested_by, title='Faculty substitution reviewed', message=f'{entry.subject}: Approved. {note}'[:1000], category='Substitution'))
                    record_audit('faculty_substitution.approved', 'FacultySubstitution', item.id, note)
                    db.session.commit()
                    flash('Substitution approved. Update the official timetable through the authorized timetable workflow if the change should take effect.', 'success')
                else:
                    item.status = 'Rejected'
                    item.reviewed_by = current_user.id
                    item.review_note = note
                    record_audit('faculty_substitution.rejected', 'FacultySubstitution', item.id, note)
                    db.session.commit()
                    flash('Substitution rejected.', 'success')
                return redirect(url_for('academic_services'))
            if kind == 'invigilator':
                require_roles(*managers)
                exam = db.session.get(ExamSchedule, request.form.get('exam_id', type=int))
                faculty = db.session.get(User, request.form.get('faculty_user_id', type=int))
                if not exam or not faculty or faculty.role != 'faculty':
                    flash('Choose a valid exam and faculty member.', 'error')
                else:
                    # Check assignments to other exams with an overlapping date/time.
                    assigned = InvigilatorAssignment.query.join(ExamSchedule).filter(InvigilatorAssignment.faculty_user_id == faculty.id, ExamSchedule.exam_date == exam.exam_date, ExamSchedule.start_time < exam.end_time, ExamSchedule.end_time > exam.start_time).first()
                    if assigned:
                        flash('That faculty member is already assigned to an overlapping exam.', 'error')
                    else:
                        db.session.add(InvigilatorAssignment(exam_id=exam.id, faculty_user_id=faculty.id, assigned_by=current_user.id))
                        record_audit('invigilator.assigned', 'ExamSchedule', exam.id, faculty.email)
                        db.session.commit()
                        flash('Invigilator assigned after conflict check.', 'success')
                return redirect(url_for('academic_services'))
            if kind == 'notification_read':
                notice = db.session.get(InAppNotification, request.form.get('notification_id', type=int))
                if not notice or notice.user_id != current_user.id:
                    abort(404)
                notice.read_at = datetime.now(timezone.utc)
                db.session.commit()
                return redirect(url_for('academic_services'))
            abort(400, description='Unknown academic-services action.')

        request_query = ServiceRequest.query
        if current_user.role not in managers:
            request_query = request_query.filter(ServiceRequest.requester_id == current_user.id)
        requests_list = request_query.order_by(ServiceRequest.created_at.desc()).limit(200).all()
        faculty = User.query.filter_by(role='faculty').order_by(User.name).all()
        exams = ExamSchedule.query.order_by(ExamSchedule.exam_date, ExamSchedule.start_time).all()
        entries = TimetableEntry.query.order_by(TimetableEntry.day_of_week, TimetableEntry.start_time).all()
        substitutions_query = FacultySubstitution.query
        if current_user.role not in managers:
            substitutions_query = substitutions_query.filter(FacultySubstitution.requested_by == current_user.id)
        substitutions = substitutions_query.order_by(FacultySubstitution.created_at.desc()).limit(200).all()
        calendar_query = AcademicCalendarItem.query
        if current_user.role == 'student':
            calendar_query = calendar_query.filter(AcademicCalendarItem.audience.in_(('All', 'Students')))
        elif current_user.role == 'faculty':
            calendar_query = calendar_query.filter(AcademicCalendarItem.audience.in_(('All', 'Faculty')))
        calendar_items = calendar_query.order_by(AcademicCalendarItem.start_date).limit(300).all()
        notifications = InAppNotification.query.filter_by(user_id=current_user.id).order_by(InAppNotification.created_at.desc()).limit(50).all()
        assignments = InvigilatorAssignment.query.order_by(InvigilatorAssignment.created_at.desc()).limit(300).all()
        return render_template('academic_services.html', requests_list=requests_list, faculty=faculty, exams=exams, entries=entries,
            substitutions=substitutions, calendar_items=calendar_items, notifications=notifications, assignments=assignments,
            can_manage=current_user.role in managers, can_request_substitution=current_user.role in staff_roles,
            today=datetime.now().date().isoformat())

    @app.get('/reports')
    @login_required
    def reports():
        managers = ('coordinator', 'admin')
        # Aggregate counts only; record-level information remains behind role/ownership checks.
        own_scenarios = Scenario.query.filter_by(user_id=current_user.id)
        if current_user.role in ('coordinator', 'admin'):
            own_scenarios = Scenario.query
        scenarios = own_scenarios.all()
        all_impacts = [impact for scenario in scenarios for impact in scenario.impacts]
        open_requests = ServiceRequest.query.filter(ServiceRequest.status.in_(('Open', 'In progress', 'Waiting for student'))).count() if current_user.role in ('coordinator', 'admin') else ServiceRequest.query.filter_by(requester_id=current_user.id).filter(ServiceRequest.status.in_(('Open', 'In progress', 'Waiting for student'))).count()
        return render_template('reports.html', scenarios=scenarios, impact_count=len(all_impacts), high_count=sum(1 for impact in all_impacts if impact.severity == 'High'), open_requests=open_requests,
            timetable_count=TimetableEntry.query.count(), exams_count=ExamSchedule.query.count(), pending_substitutions=FacultySubstitution.query.filter_by(status='Pending').count() if current_user.role in managers else FacultySubstitution.query.filter_by(requested_by=current_user.id, status='Pending').count())

    @app.get('/scenarios/compare')
    @login_required
    def compare_scenarios():
        ids = []
        for value in request.args.getlist('id')[:4]:
            try:
                ids.append(int(value))
            except (ValueError, TypeError):
                continue
        selected = Scenario.query.filter(Scenario.id.in_(ids)).all() if ids else []
        selected = [scenario for scenario in selected if scenario.user_id == current_user.id or current_user.role in ('coordinator', 'admin')]
        available_query = Scenario.query if current_user.role in ('coordinator', 'admin') else Scenario.query.filter_by(user_id=current_user.id)
        return render_template('scenario_compare.html', scenarios=selected, available=available_query.order_by(Scenario.updated_at.desc()).limit(100).all())

    @app.get('/reports/impact-summary.csv')
    @login_required
    def export_impact_summary():
        scenarios = Scenario.query.order_by(Scenario.updated_at.desc()).all() if current_user.role in ('coordinator', 'admin') else Scenario.query.filter_by(user_id=current_user.id).order_by(Scenario.updated_at.desc()).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Scenario ID', 'Title', 'Domain', 'Variable', 'Current value', 'Proposed value', 'Status', 'Impact count', 'High impacts', 'Evidence-backed impacts'])
        for scenario in scenarios:
            writer.writerow([scenario.id, scenario.title, scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.status, len(scenario.impacts), sum(1 for impact in scenario.impacts if impact.severity == 'High'), sum(1 for impact in scenario.impacts if 'evidence' in impact.source.lower())])
        response = make_response('\ufeff' + output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="campusripple-impact-summary.csv"'
        return response

    @app.get('/admin/audit')
    @login_required
    def admin_audit():
        require_roles('admin')
        query_text = request.args.get('q', '').strip()[:100]
        query = AuditEvent.query
        if query_text:
            pattern = f'%{query_text}%'
            query = query.outerjoin(User, AuditEvent.user_id == User.id).filter(or_(
                AuditEvent.action.ilike(pattern), AuditEvent.entity_type.ilike(pattern),
                AuditEvent.details.ilike(pattern), User.email.ilike(pattern)))
        page = max(1, request.args.get('page', 1, type=int) or 1)
        per_page = 50
        total_events = query.count()
        pages = max(1, (total_events + per_page - 1) // per_page)
        page = min(page, pages)
        events = query.order_by(AuditEvent.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return render_template('audit_log.html', events=events, q=query_text, page=page, pages=pages, total_events=total_events)

    @app.get('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('landing.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            if not name or len(name) > 80:
                flash('Enter a name up to 80 characters.', 'error')
            elif len(email) > 254 or not is_eligible_college_email(email):
                flash('Only members of ACE Engineering College are eligible to register.', 'error')
                return render_template('auth.html', mode='register')
            elif len(password) < 12:
                flash('Use a password with at least 12 characters.', 'error')
            elif User.query.filter_by(email=email).first():
                flash('An account with that email already exists.', 'error')
            else:
                user = User(name=name, email=email)
                # Public registration always creates a student. Provision administrators with `flask create-admin`.
                user.set_password(password)
                if app.config.get('REQUIRE_EMAIL_VERIFICATION'):
                    token = secrets.token_urlsafe(32)
                    user.email_verification_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
                    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
                else:
                    user.email_verified_at = datetime.now(timezone.utc)
                db.session.add(user)
                db.session.commit()
                if app.config.get('REQUIRE_EMAIL_VERIFICATION'):
                    verify_path = url_for('verify_email', token=token, _external=False)
                    if not send_account_email(app, user.email, verify_path, verification=True):
                        db.session.delete(user)
                        db.session.commit()
                        flash('Email verification could not be sent. Please try again later or contact the administrator.', 'error')
                        return render_template('auth.html', mode='register'), 503
                    flash('Account created. Check your email for the verification link before logging in.', 'success')
                    return redirect(url_for('auth_login'))
                login_user(user)
                session.pop('_csrf_token', None)
                flash('Your account is ready. Create your first decision analysis.', 'success')
                return redirect(url_for('dashboard'))
        return render_template('auth.html', mode='register')

    @app.get('/verify-email/<token>')
    def verify_email(token):
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        user = User.query.filter_by(email_verification_token_hash=token_hash).first()
        now = datetime.now(timezone.utc)
        if not user or not is_eligible_college_email(user.email) or not user.email_verification_expires_at or as_utc(user.email_verification_expires_at) <= now:
            return render_template('error.html', code=400, message='This verification link is invalid or has expired.'), 400
        user.email_verified_at = now
        user.email_verification_token_hash = None
        user.email_verification_expires_at = None
        db.session.commit()
        flash('Email verified. You can now log in.', 'success')
        return redirect(url_for('auth_login'))

    @app.post('/resend-verification')
    def resend_verification():
        email = request.form.get('email', '').strip().lower()[:254]
        user = User.query.filter_by(email=email).first() if email and is_eligible_college_email(email) else None
        now = datetime.now(timezone.utc)
        recently_sent = bool(user and user.email_verification_expires_at and
                             as_utc(user.email_verification_expires_at) > now + timedelta(hours=23, minutes=55))
        if app.config.get('REQUIRE_EMAIL_VERIFICATION') and user and user.email_verified_at is None and not recently_sent:
            token = secrets.token_urlsafe(32)
            user.email_verification_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
            user.email_verification_expires_at = now + timedelta(hours=24)
            db.session.commit()
            verify_path = url_for('verify_email', token=token, _external=False)
            if not send_account_email(app, user.email, verify_path, verification=True):
                user.email_verification_token_hash = None
                user.email_verification_expires_at = None
                db.session.commit()
        flash('If the account requires verification, a new link will be sent when email delivery is available.', 'success')
        return redirect(url_for('auth_login'))

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            # Always show the same message to avoid disclosing registered accounts.
            user = User.query.filter_by(email=email).first() if len(email) <= 254 and is_eligible_college_email(email) else None
            now = datetime.now(timezone.utc)
            if user:
                last_request = user.reset_token_expires_at
                # The expiry field also acts as a short-lived request throttle while a token is active.
                if not user.reset_token_hash or not last_request or last_request <= now:
                    token = secrets.token_urlsafe(32)
                    user.reset_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
                    user.reset_token_expires_at = now + timedelta(minutes=30)
                    db.session.commit()
                    reset_url = url_for('reset_password', token=token, _external=False)
                    delivered = send_password_reset_email(app, user.email, reset_url)
                    if not delivered:
                        # Allow a fresh request after fixing SMTP configuration.
                        user.reset_token_hash = None
                        user.reset_token_expires_at = None
                        db.session.commit()
            flash('If an account matches that email, password reset instructions will be sent if email delivery is configured.', 'success')
            return redirect(url_for('auth_login'))
        return render_template('forgot_password.html')

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        if current_user.is_authenticated:
            logout_user()
            session.clear()
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        user = User.query.filter_by(reset_token_hash=token_hash).first()
        now = datetime.now(timezone.utc)
        if (not user or not is_eligible_college_email(user.email) or
                not user.reset_token_expires_at or as_utc(user.reset_token_expires_at) <= now):
            return render_template('reset_password.html', invalid=True), 400
        if request.method == 'POST':
            password = request.form.get('password', '')
            confirmation = request.form.get('confirm_password', '')
            if len(password) < 12:
                flash('Use a password with at least 12 characters.', 'error')
            elif password != confirmation:
                flash('The passwords do not match.', 'error')
            else:
                user.set_password(password)
                user.reset_token_hash = None
                user.reset_token_expires_at = None
                db.session.commit()
                flash('Password updated. Log in with your new password.', 'success')
                return redirect(url_for('auth_login'))
        return render_template('reset_password.html', invalid=False)

    @app.route('/login', methods=['GET', 'POST'])
    def auth_login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()[:254]
            password = request.form.get('password', '')
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(minutes=15)
            # HMAC identifiers allow shared-database throttling across app workers without
            # retaining raw email addresses or IP addresses in the attempt table.
            secret = str(app.config.get('SECRET_KEY', ''))
            email_digest = hmac.new(secret.encode('utf-8'), ('email|' + email).encode('utf-8'), hashlib.sha256).hexdigest()
            remote_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip() if app.config.get('TRUST_PROXY_HEADERS') else (request.remote_addr or 'unknown')
            ip_digest = hmac.new(secret.encode('utf-8'), ('ip|' + remote_ip).encode('utf-8'), hashlib.sha256).hexdigest()
            recent_failures = LoginAttempt.query.filter(
                LoginAttempt.attempted_at >= window_start,
                LoginAttempt.succeeded.is_(False),
                or_(LoginAttempt.email_digest == email_digest, LoginAttempt.ip_digest == ip_digest)
            ).count()
            if recent_failures >= 8:
                # Keep response generic to avoid disclosing whether an account exists.
                flash('Too many sign-in attempts. Wait 15 minutes and try again.', 'error')
                return render_template('auth.html', mode='login'), 429
            user = User.query.filter_by(email=email).first() if is_eligible_college_email(email) else None
            valid_credentials = bool(user and user.check_password(password))
            unverified_account = bool(valid_credentials and app.config.get('REQUIRE_EMAIL_VERIFICATION') and user.email_verified_at is None)
            succeeded = valid_credentials and not unverified_account
            if unverified_account:
                flash('Please verify your email before logging in. Use the resend-verification option if needed.', 'error')
            db.session.add(LoginAttempt(email_digest=email_digest, ip_digest=ip_digest, succeeded=succeeded, attempted_at=now))
            # Periodic bounded cleanup avoids unbounded growth without storing identifiers elsewhere.
            LoginAttempt.query.filter(LoginAttempt.attempted_at < now - timedelta(days=2)).delete(synchronize_session=False)
            db.session.commit()
            if succeeded:
                login_user(user)
                session.pop('_csrf_token', None)
                return redirect(url_for('dashboard'))
            if not unverified_account:
                flash('Email or password is incorrect.', 'error')
        return render_template('auth.html', mode='login')

    @app.post('/logout')
    @login_required
    def logout():
        logout_user()
        session.clear()
        return redirect(url_for('index'))

    @app.get('/dashboard')
    @login_required
    def dashboard():
        query_text = request.args.get('q', '').strip()[:100]
        query = Scenario.query.filter_by(user_id=current_user.id)
        if query_text:
            pattern = f'%{query_text}%'
            query = query.filter(or_(Scenario.title.ilike(pattern), Scenario.domain.ilike(pattern),
                                     Scenario.change_variable.ilike(pattern), Scenario.context.ilike(pattern)))
        total = query.count()
        analyzed = query.filter_by(status='Analyzed').count()
        page = max(1, request.args.get('page', 1, type=int) or 1)
        per_page = 20
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, pages)
        scenarios = query.order_by(Scenario.updated_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return render_template('dashboard.html', scenarios=scenarios, total=total, analyzed=analyzed,
                               q=query_text, page=page, pages=pages)

    @app.route('/scenarios/new', methods=['GET', 'POST'])
    @login_required
    def new_scenario():
        if request.method == 'POST':
            data, error = scenario_form_data(request.form)
            if error:
                flash(error, 'error')
            else:
                scenario = Scenario(user_id=current_user.id, **data)
                db.session.add(scenario)
                db.session.flush()
                record_audit('scenario.created', 'Scenario', scenario.id, scenario.title)
                db.session.commit()
                flash('Decision saved. Run the analysis to trace its impact chain.', 'success')
                return redirect(url_for('scenario_detail', scenario_id=scenario.id))
        return render_template('scenario_form.html', scenario=None)

    @app.route('/scenarios/<int:scenario_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_scenario(scenario_id):
        scenario = owned_scenario(scenario_id)
        if request.method == 'POST':
            data, error = scenario_form_data(request.form)
            if error:
                flash(error, 'error')
            else:
                for key, value in data.items():
                    setattr(scenario, key, value)
                scenario.status = 'Draft'
                scenario.impacts.clear()
                record_audit('scenario.updated', 'Scenario', scenario.id, scenario.title)
                db.session.commit()
                flash('Decision updated. Run analysis again to refresh its impacts.', 'success')
                return redirect(url_for('scenario_detail', scenario_id=scenario.id))
        return render_template('scenario_form.html', scenario=scenario)

    @app.get('/scenarios/<int:scenario_id>')
    @login_required
    def scenario_detail(scenario_id):
        scenario = db.session.get(Scenario, scenario_id)
        if not scenario or (scenario.user_id != current_user.id and current_user.role not in ('coordinator', 'admin')):
            abort(404)
        return render_template('scenario_detail.html', scenario=scenario)

    @app.post('/scenarios/<int:scenario_id>/actions')
    @login_required
    def add_mitigation_action(scenario_id):
        scenario = owned_scenario(scenario_id)
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        owner_name = (request.form.get('owner_name') or 'Unassigned').strip() or 'Unassigned'
        priority = (request.form.get('priority') or 'Medium').strip()
        impact_raw = (request.form.get('impact_id') or '').strip()
        due_raw = (request.form.get('due_at') or '').strip()
        if not title or len(title) > 160 or len(description) > 1600 or len(owner_name) > 120:
            flash('Enter a task title and keep all fields within their length limits.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase7-actions')
        if priority not in {'Critical','High','Medium','Low'}:
            abort(400)
        impact = None
        if impact_raw:
            try: impact = Impact.query.filter_by(id=int(impact_raw), scenario_id=scenario.id).first()
            except ValueError: impact = None
            if impact is None: abort(400)
        due_at = _parse_optional_utc_datetime(due_raw)
        if due_raw and due_at is None:
            flash('Due date is invalid.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase7-actions')
        action = MitigationAction(scenario_id=scenario.id, impact_id=impact.id if impact else None,
            created_by_id=current_user.id, title=title, description=description, owner_name=owner_name,
            priority=priority, status='Open', due_at=due_at)
        db.session.add(action)
        record_audit('mitigation.created', 'MitigationAction', None, title)
        db.session.commit()
        flash('Mitigation task created.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase7-actions')

    @app.post('/scenarios/<int:scenario_id>/actions/<int:action_id>')
    @login_required
    def update_mitigation_action(scenario_id, action_id):
        scenario = owned_scenario(scenario_id)
        action = MitigationAction.query.filter_by(id=action_id, scenario_id=scenario.id).first_or_404()
        status = (request.form.get('status') or '').strip()
        note = (request.form.get('completion_note') or '').strip()
        if status not in {'Open','In Progress','Blocked','Completed','Cancelled'} or len(note) > 1200:
            abort(400)
        action.status = status
        action.completion_note = note
        record_audit('mitigation.updated', 'MitigationAction', action.id, f'{status}: {action.title}')
        db.session.commit()
        flash('Mitigation task updated.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase7-actions')

    @app.post('/scenarios/<int:scenario_id>/evidence')
    @login_required
    def add_scenario_evidence(scenario_id):
        scenario = owned_scenario(scenario_id)
        label = (request.form.get('label') or '').strip()
        source_type = (request.form.get('source_type') or 'Manual').strip()
        source_ref = (request.form.get('source_ref') or '').strip()
        status = (request.form.get('status') or 'Unverified').strip()
        notes = (request.form.get('notes') or '').strip()
        try:
            confidence = int(request.form.get('confidence', '50'))
        except (TypeError, ValueError):
            confidence = -1
        allowed_status = {'Verified', 'Unverified', 'Disputed', 'Stale'}
        allowed_source = {'Manual', 'Official record', 'Sensor', 'Email', 'External system', 'Assumption'}
        if not label or len(label) > 140 or len(source_ref) > 240 or len(notes) > 1200:
            flash('Evidence needs a label (1–140 characters); source and notes must fit their limits.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        if status not in allowed_status or source_type not in allowed_source or not 0 <= confidence <= 100:
            flash('Choose valid evidence status, source type, and confidence from 0 to 100.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        observed_at = _parse_optional_utc_datetime(request.form.get('observed_at'))
        valid_until = _parse_optional_utc_datetime(request.form.get('valid_until'))
        if request.form.get('observed_at') and observed_at is None or request.form.get('valid_until') and valid_until is None:
            flash('Evidence timestamps must be valid dates and times.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        if observed_at and valid_until and valid_until < observed_at:
            flash('Evidence expiry cannot be earlier than its observation time.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        record = ScenarioEvidence(scenario_id=scenario.id, created_by_id=current_user.id, label=label,
                                  source_type=source_type, source_ref=source_ref, status=status,
                                  confidence=confidence, observed_at=observed_at, valid_until=valid_until, notes=notes)
        db.session.add(record)
        scenario.status = 'Draft'
        scenario.analysis_inputs_json = None
        scenario.analysis_input_hash = None
        scenario.analysis_result_hash = None
        record_audit('scenario.evidence_added', 'ScenarioEvidence', None, f'scenario={scenario.id}; label={label[:80]}')
        db.session.commit()
        flash('Evidence saved. Re-run analysis so confidence and freshness are reflected in the conclusions.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')

    @app.post('/scenarios/<int:scenario_id>/evidence/<int:evidence_id>/update')
    @login_required
    def update_scenario_evidence(scenario_id, evidence_id):
        scenario = owned_scenario(scenario_id)
        record = ScenarioEvidence.query.filter_by(id=evidence_id, scenario_id=scenario.id).first_or_404()
        status = (request.form.get('status') or '').strip()
        try:
            confidence = int(request.form.get('confidence', '-1'))
        except (TypeError, ValueError):
            confidence = -1
        if status not in {'Verified', 'Unverified', 'Disputed', 'Stale'} or not 0 <= confidence <= 100:
            flash('Choose a valid status and confidence between 0 and 100.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        record.status = status
        record.confidence = confidence
        record.source_ref = (request.form.get('source_ref') or '').strip()[:240]
        record.notes = (request.form.get('notes') or '').strip()[:1200]
        record.observed_at = _parse_optional_utc_datetime(request.form.get('observed_at'))
        record.valid_until = _parse_optional_utc_datetime(request.form.get('valid_until'))
        if request.form.get('observed_at') and record.observed_at is None or request.form.get('valid_until') and record.valid_until is None:
            flash('Evidence timestamps must be valid dates and times.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        if record.observed_at and record.valid_until and record.valid_until < record.observed_at:
            flash('Evidence expiry cannot be earlier than its observation time.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        scenario.status = 'Draft'
        scenario.analysis_inputs_json = None
        scenario.analysis_input_hash = None
        scenario.analysis_result_hash = None
        record_audit('scenario.evidence_updated', 'ScenarioEvidence', record.id, f'scenario={scenario.id}; status={status}; confidence={confidence}')
        db.session.commit()
        flash('Evidence updated. Re-run analysis to refresh conclusions.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')

    @app.post('/scenarios/<int:scenario_id>/evidence/<int:evidence_id>/delete')
    @login_required
    def delete_scenario_evidence(scenario_id, evidence_id):
        scenario = owned_scenario(scenario_id)
        record = ScenarioEvidence.query.filter_by(id=evidence_id, scenario_id=scenario.id).first_or_404()
        db.session.delete(record)
        scenario.status = 'Draft'
        scenario.analysis_inputs_json = None
        scenario.analysis_input_hash = None
        scenario.analysis_result_hash = None
        record_audit('scenario.evidence_removed', 'ScenarioEvidence', evidence_id, f'scenario={scenario.id}')
        db.session.commit()
        flash('Evidence removed. Re-run analysis to refresh the result.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')

    @app.post('/scenarios/<int:scenario_id>/sensitivity')
    @login_required
    def scenario_sensitivity(scenario_id):
        scenario = owned_scenario(scenario_id)
        evidence_id = request.form.get('evidence_id', type=int)
        assumed_status = (request.form.get('assumed_status') or '').strip()
        record = ScenarioEvidence.query.filter_by(id=evidence_id, scenario_id=scenario.id).first() if evidence_id else None
        if not record or assumed_status not in {'Verified', 'Unverified', 'Disputed', 'Stale'}:
            flash('Choose an evidence item and a valid alternative status.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id) + '#phase6-evidence')
        baseline_records = list(scenario.evidence_records)
        baseline = _evidence_items_from_payloads([_scenario_evidence_payload(item) for item in baseline_records])
        alternate_records = []
        for item in baseline_records:
            payload = _scenario_evidence_payload(item)
            if item.id == record.id:
                payload['status'] = assumed_status
                if assumed_status == 'Verified':
                    payload['confidence'] = max(80, payload['confidence'])
                elif assumed_status in ('Disputed', 'Stale'):
                    payload['confidence'] = min(35, payload['confidence'])
            alternate_records.append(payload)
        before = analyze(scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.context,
                         collect_impact_evidence(scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.context) + baseline)
        after = analyze(scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.context,
                        collect_impact_evidence(scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.context) + _evidence_items_from_payloads(alternate_records))
        from .evidence import compare_impacts
        comparison = compare_impacts(before, after)
        record_audit('scenario.evidence_sensitivity', 'ScenarioEvidence', record.id, f'scenario={scenario.id}; status={assumed_status}')
        db.session.commit()
        return render_template('scenario_sensitivity.html', scenario=scenario, evidence=record, assumed_status=assumed_status, comparison=comparison)

    @app.post('/impacts/<int:impact_id>/feedback')
    @login_required
    def impact_feedback(impact_id):
        impact = db.session.get(Impact, impact_id)
        if not impact:
            abort(404)
        scenario = impact.scenario
        if scenario.user_id != current_user.id and current_user.role not in ('coordinator', 'admin'):
            abort(404)
        assessment = request.form.get('assessment', '').strip()
        observed_outcome = request.form.get('observed_outcome', '').strip()
        if assessment not in ('Confirmed', 'Incorrect', 'Uncertain'):
            flash('Choose a valid impact assessment.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id))
        if len(observed_outcome) > 1200:
            flash('Observed outcome must be 1,200 characters or fewer.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id))
        feedback = ImpactFeedback.query.filter_by(impact_id=impact.id, user_id=current_user.id).first()
        if feedback is None:
            feedback = ImpactFeedback(impact_id=impact.id, user_id=current_user.id)
            db.session.add(feedback)
        feedback.assessment = assessment
        feedback.observed_outcome = observed_outcome
        feedback.analysis_version = scenario.analysis_version or 'unknown'
        record_audit('impact.feedback_submitted', 'Impact', impact.id, f'assessment={assessment}; scenario={scenario.id}')
        db.session.commit()
        flash('Thank you. Your impact review has been recorded for quality evaluation.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id) + f'#impact-{impact.id}')

    @app.get('/admin/impact-quality/export.csv')
    @login_required
    def admin_impact_quality_export():
        require_roles('admin')
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['feedback_id', 'impact_id', 'scenario_id', 'analysis_version', 'assessment',
                         'impact_source', 'impact_level', 'severity', 'evidence_ref', 'observed_outcome',
                         'created_at_utc', 'updated_at_utc'])
        for feedback in ImpactFeedback.query.order_by(ImpactFeedback.created_at.asc()).yield_per(500):
            impact = feedback.impact
            writer.writerow([feedback.id, feedback.impact_id, impact.scenario_id, feedback.analysis_version,
                             feedback.assessment, impact.source, impact.level, impact.severity,
                             impact.evidence_ref or '', feedback.observed_outcome,
                             feedback.created_at.isoformat() if feedback.created_at else '',
                             feedback.updated_at.isoformat() if feedback.updated_at else ''])
        response = make_response('\ufeff' + output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="campusripple-impact-feedback-evaluation.csv"'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/admin/impact-quality')
    @login_required
    def admin_impact_quality():
        require_roles('admin')
        total = ImpactFeedback.query.count()
        confirmed = ImpactFeedback.query.filter_by(assessment='Confirmed').count()
        incorrect = ImpactFeedback.query.filter_by(assessment='Incorrect').count()
        uncertain = ImpactFeedback.query.filter_by(assessment='Uncertain').count()
        latest = ImpactFeedback.query.order_by(ImpactFeedback.updated_at.desc()).limit(100).all()
        # This is feedback coverage, not a statistically validated model-accuracy score.
        return render_template('admin_impact_quality.html', total=total, confirmed=confirmed,
                               incorrect=incorrect, uncertain=uncertain, latest=latest)

    @app.post('/scenarios/<int:scenario_id>/analyze')
    @login_required
    def analyze_scenario(scenario_id):
        scenario = owned_scenario(scenario_id)
        evidence = collect_impact_evidence(scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.context)
        evidence_records = [_scenario_evidence_payload(item) for item in scenario.evidence_records]
        evidence.extend(_evidence_items_from_payloads(evidence_records))
        inputs = {
            'schema_version': 'phase6-input-v1',
            'rule_version': RULE_VERSION,
            'scenario': {'title': scenario.title, 'domain': scenario.domain,
                         'change_variable': scenario.change_variable, 'current_value': scenario.current_value,
                         'proposed_value': scenario.proposed_value, 'context': scenario.context},
            'evidence': evidence,
            'evidence_records': evidence_records,
        }
        result = analyze(scenario.domain, scenario.change_variable, scenario.current_value, scenario.proposed_value, scenario.context, evidence)
        scenario.impacts.clear()
        db.session.flush()
        for item in result:
            db.session.add(Impact(scenario_id=scenario.id, **item))
        scenario.analysis_inputs_json = _canonical_json(inputs)
        scenario.analysis_input_hash = _sha256_json(inputs)
        scenario.analysis_result_hash = _sha256_json([_impact_snapshot(item) for item in result])
        scenario.status = 'Analyzed'
        scenario.analysis_version = RULE_VERSION
        scenario.analyzed_at = datetime.now(timezone.utc)
        record_audit('scenario.analyzed', 'Scenario', scenario.id, scenario.title)
        db.session.commit()
        flash('Analysis completed. Review the impact chain and validate assumptions before acting.', 'success')
        return redirect(url_for('scenario_detail', scenario_id=scenario.id))

    @app.get('/scenarios/<int:scenario_id>/verify-analysis')
    @login_required
    def verify_scenario_analysis(scenario_id):
        scenario = owned_scenario(scenario_id)
        if not scenario.analysis_inputs_json or not scenario.analysis_input_hash or not scenario.analysis_result_hash:
            return {'verified': False, 'status': 'legacy_analysis',
                    'message': 'This analysis predates reproducibility snapshots. Re-run analysis to create one.'}, 409
        try:
            inputs = json.loads(scenario.analysis_inputs_json)
        except (TypeError, ValueError):
            return {'verified': False, 'status': 'invalid_snapshot', 'message': 'Stored input snapshot is not valid JSON.'}, 409
        input_hash_matches = _sha256_json(inputs) == scenario.analysis_input_hash
        replay = analyze(inputs['scenario']['domain'], inputs['scenario']['change_variable'],
                         inputs['scenario']['current_value'], inputs['scenario']['proposed_value'],
                         inputs['scenario'].get('context', ''), inputs.get('evidence', []))
        replay_hash = _sha256_json([_impact_snapshot(item) for item in replay])
        stored_hash_matches = _sha256_json([_impact_snapshot(item) for item in scenario.impacts]) == scenario.analysis_result_hash
        replay_matches = replay_hash == scenario.analysis_result_hash
        return {
            'verified': bool(input_hash_matches and stored_hash_matches and replay_matches),
            'status': 'verified' if input_hash_matches and stored_hash_matches and replay_matches else 'mismatch',
            'analysis_version': scenario.analysis_version,
            'analyzed_at': scenario.analyzed_at.isoformat() if scenario.analyzed_at else None,
            'input_hash': scenario.analysis_input_hash,
            'stored_result_hash': scenario.analysis_result_hash,
            'replayed_result_hash': replay_hash,
            'checks': {'input_snapshot_integrity': input_hash_matches,
                       'stored_result_integrity': stored_hash_matches,
                       'deterministic_replay_match': replay_matches},
            'message': 'Hashes confirm the saved input, saved impacts, and deterministic replay match.' if input_hash_matches and stored_hash_matches and replay_matches else 'The saved analysis did not pass every integrity check. Re-run and review before relying on it.'
        }

    @app.post('/scenarios/<int:scenario_id>/simulate')
    @login_required
    def simulate_scenario(scenario_id):
        scenario = owned_scenario(scenario_id)
        alternative = request.form.get('alternative_value', '').strip()
        if not alternative or len(alternative) > 120:
            flash('Enter an alternative value of 1–120 characters.', 'error')
            return redirect(url_for('scenario_detail', scenario_id=scenario.id))
        evidence = collect_impact_evidence(scenario.domain, scenario.change_variable, scenario.current_value, alternative, scenario.context)
        simulation_impacts = analyze(scenario.domain, scenario.change_variable, scenario.current_value, alternative, scenario.context, evidence)
        baseline_impacts = analyze(scenario.domain, scenario.change_variable, scenario.current_value,
                                   scenario.proposed_value, scenario.context,
                                   collect_impact_evidence(scenario.domain, scenario.change_variable,
                                                           scenario.current_value, scenario.proposed_value,
                                                           scenario.context))
        from .evidence import compare_impacts
        comparison = compare_impacts(baseline_impacts, simulation_impacts)
        baseline_high_count = sum(1 for item in baseline_impacts if item['severity'] == 'High')
        alternative_high_count = sum(1 for item in simulation_impacts if item['severity'] == 'High')
        if alternative_high_count < baseline_high_count:
            recommendation = 'The alternative has fewer high-severity items under the current rules/evidence. Prefer it for review, then verify feasibility and all remaining constraints before approval.'
        elif alternative_high_count > baseline_high_count:
            recommendation = 'The alternative introduces more high-severity items under the current rules/evidence. Do not prefer it without a documented mitigation or a better alternative.'
        elif len(comparison['new']) < len(comparison['resolved']):
            recommendation = 'The alternative removes more detected item signatures than it adds. Review remaining and new items, confirm data freshness, and verify feasibility before approval.'
        else:
            recommendation = 'The available evidence does not establish that this alternative is safer. Compare another date, time, resource or capacity and verify all constraints before approval.'
        summary = {
            'recommendation': recommendation,
            'high': alternative_high_count,
            'medium': sum(1 for item in simulation_impacts if item['severity'] == 'Medium'),
            'low': sum(1 for item in simulation_impacts if item['severity'] == 'Low'),
            'evidence_count': len(evidence),
            'baseline_high': sum(1 for item in baseline_impacts if item['severity'] == 'High'),
            'baseline_medium': sum(1 for item in baseline_impacts if item['severity'] == 'Medium'),
            'baseline_low': sum(1 for item in baseline_impacts if item['severity'] == 'Low'),
            'baseline_evidence_count': sum(1 for item in baseline_impacts if 'evidence' in item.get('source', '').lower()),
            'alternative_high_delta': alternative_high_count - baseline_high_count,
            'resolved': comparison['resolved'],
            'remaining': comparison['remaining'],
            'new': comparison['new'],
            'baseline_count': comparison['baseline_count'],
            'alternative_count': comparison['alternative_count'],
        }
        record_audit('scenario.simulated', 'Scenario', scenario.id, f'alternative={alternative[:100]}')
        db.session.commit()
        return render_template('simulation_result.html', scenario=scenario, alternative=alternative,
                               impacts=simulation_impacts, summary=summary)

    @app.post('/scenarios/<int:scenario_id>/delete')
    @login_required
    def delete_scenario(scenario_id):
        scenario = owned_scenario(scenario_id)
        record_audit('scenario.deleted', 'Scenario', scenario.id, scenario.title)
        db.session.delete(scenario)
        db.session.commit()
        flash('Decision analysis deleted.', 'success')
        return redirect(url_for('dashboard'))

    @app.get('/scenarios/<int:scenario_id>/export.csv')
    @login_required
    def export_csv(scenario_id):
        scenario = owned_scenario(scenario_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Scenario', scenario.title])
        writer.writerow(['Domain', scenario.domain])
        writer.writerow(['Proposed change', f'{scenario.change_variable}: {scenario.current_value} -> {scenario.proposed_value}'])
        writer.writerow(['Rule version', scenario.analysis_version or 'Not analyzed'])
        writer.writerow(['Analyzed at (UTC)', scenario.analyzed_at.isoformat() if scenario.analyzed_at else ''])
        writer.writerow([])
        writer.writerow(['Level', 'Activity', 'Impact', 'Parent activity', 'Cause', 'Severity', 'Likelihood', 'Mitigation', 'Source', 'Evidence reference', 'Rule version', 'Analyzed at (UTC)'])
        for impact in scenario.impacts:
            writer.writerow([impact.level, impact.activity, impact.description, impact.parent_activity, impact.cause, impact.severity, impact.likelihood, impact.mitigation, impact.source, impact.evidence_ref or '', scenario.analysis_version or '', scenario.analyzed_at.isoformat() if scenario.analyzed_at else ''])
        response = make_response('\ufeff' + output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="decision-{scenario.id}-impact-report.csv"'
        return response

    @app.get('/scenarios/<int:scenario_id>/export.json')
    @login_required
    def export_json(scenario_id):
        scenario = owned_scenario(scenario_id)
        payload = {
            'schema_version': '1.0',
            'scenario': {
                'id': scenario.id,
                'title': scenario.title,
                'domain': scenario.domain,
                'change': {
                    'variable': scenario.change_variable,
                    'current_value': scenario.current_value,
                    'proposed_value': scenario.proposed_value,
                },
                'context': scenario.context,
                'status': scenario.status,
                'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
                'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None,
                'analyzed_at': scenario.analyzed_at.isoformat() if scenario.analyzed_at else None,
                'analysis_version': scenario.analysis_version,
                'analysis_input_hash': scenario.analysis_input_hash,
                'analysis_result_hash': scenario.analysis_result_hash,
                'reproducibility_snapshot_available': bool(scenario.analysis_inputs_json),
            },
            'summary': {
                'total_impacts': len(scenario.impacts),
                'direct_impacts': sum(1 for item in scenario.impacts if item.level == 1),
                'level_2_impacts': sum(1 for item in scenario.impacts if item.level == 2),
                'level_3_impacts': sum(1 for item in scenario.impacts if item.level == 3),
                'high_severity': sum(1 for item in scenario.impacts if item.severity == 'High'),
            },
            'impacts': [{
                'level': item.level,
                'activity': item.activity,
                'description': item.description,
                'parent_activity': item.parent_activity,
                'cause': item.cause,
                'severity': item.severity,
                'likelihood': item.likelihood,
                'mitigation': item.mitigation,
                'source': item.source,
                'evidence_ref': item.evidence_ref,
            } for item in scenario.impacts],
            'interpretation_note': 'Rule-based impacts are hypotheses unless their source explicitly identifies college database evidence. Verify assumptions before acting.',
        }
        response = make_response(json.dumps(payload, ensure_ascii=False, indent=2))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="decision-{scenario.id}-impact-report.json"'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('error.html', code=400, message=getattr(error, 'description', 'Invalid request.')), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('error.html', code=403, message='You do not have permission to access this feature.'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', code=404, message='The page may have moved or you may not have access to it.'), 404


def _parse_optional_utc_datetime(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None

def _scenario_evidence_payload(record):
    return {'id': record.id, 'label': record.label, 'source_type': record.source_type,
            'source_ref': record.source_ref, 'status': record.status, 'confidence': int(record.confidence),
            'observed_at': record.observed_at.isoformat() if record.observed_at else None,
            'valid_until': record.valid_until.isoformat() if record.valid_until else None,
            'notes': record.notes, 'created_at': record.created_at.isoformat() if record.created_at else None}

def _evidence_items_from_payloads(records):
    now = datetime.now(timezone.utc)
    result = []
    for record in records:
        status = record.get('status', 'Unverified')
        confidence = max(0, min(100, int(record.get('confidence', 50) or 0)))
        stale = status == 'Stale'
        valid_until = _parse_optional_utc_datetime(record.get('valid_until'))
        observed_at = _parse_optional_utc_datetime(record.get('observed_at'))
        if valid_until and valid_until < now:
            stale = True
        if observed_at and (now - observed_at).total_seconds() > 30 * 86400 and not valid_until:
            stale = True
        verified = status == 'Verified' and confidence >= 80 and not stale
        result.append({
            'level': 1, 'activity': ('Evidence verified: ' if verified else 'Uncertain assumption: ') + str(record.get('label') or 'Unnamed evidence')[:110],
            'description': (str(record.get('notes') or 'Evidence record attached to this decision.')[:700] +
                           f" Source type: {record.get('source_type', 'Manual')}; status: {'Stale' if stale else status}; confidence: {confidence}%."),
            'cause': f"Evidence reference {record.get('source_ref') or 'not supplied'}; this input is {'treated as stronger evidence' if verified else 'not treated as confirmed fact'} until its source, freshness and confidence are validated.",
            'mitigation': 'No additional action required beyond normal source validation.' if verified else 'Verify the source with the responsible owner, refresh expired information, and rerun the analysis before relying on downstream recommendations.',
            'source': f"phase6 evidence register ({record.get('source_type', 'Manual')}; {status}; confidence {confidence}%)",
            'evidence_ref': str(record.get('source_ref') or f"scenario-evidence:{record.get('id', 'new')}")[:160],
            'severity': 'Medium', 'likelihood': 'High' if not verified else 'Medium',
            'parent_activity': 'Proposed change'})
    return result


def scenario_form_data(form):
    title = (form.get('title') or '').strip()
    domain = form.get('domain') or 'General'
    variable = form.get('change_variable') or 'Resource'
    current_value = (form.get('current_value') or '').strip()
    proposed_value = (form.get('proposed_value') or '').strip()
    context = (form.get('context') or '').strip()
    if not title or len(title) > 120:
        return None, 'Give the decision a title (up to 120 characters).'
    if domain not in DOMAINS:
        return None, 'Choose a valid domain.'
    if variable not in VARIABLES:
        return None, 'Choose a valid change variable.'
    if not current_value or not proposed_value or len(current_value) > 120 or len(proposed_value) > 120:
        return None, 'Enter current and proposed values (up to 120 characters each).'
    if len(context) > 2000:
        return None, 'Context must be 2,000 characters or fewer.'
    if current_value == proposed_value:
        return None, 'The proposed value must differ from the current value.'
    return {'title': title, 'domain': domain, 'change_variable': variable, 'current_value': current_value, 'proposed_value': proposed_value, 'context': context}, None


def owned_scenario(scenario_id):
    scenario = Scenario.query.filter_by(id=scenario_id, user_id=current_user.id).first()
    if not scenario:
        abort(404)
    return scenario


def as_utc(value):
    """SQLite may return naive datetimes; treat stored UTC values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def send_password_reset_email(app, recipient, reset_path):
    """Send a reset email using the configured SMTP server; never log the token."""
    required = ('MAIL_SERVER', 'MAIL_DEFAULT_SENDER')
    if not all(app.config.get(key) for key in required):
        app.logger.warning('Password reset requested but SMTP is not configured.')
        return False

    return send_account_email(app, recipient, reset_path, verification=False)

def send_account_email(app, recipient, path, verification=False):
    """Send account security email via SMTP without logging secrets or tokens."""
    if not app.config.get('MAIL_SERVER') or not app.config.get('MAIL_DEFAULT_SENDER'):
        app.logger.warning('Account email requested but SMTP is not configured.')
        return False
    base_url = app.config.get('PUBLIC_BASE_URL', '').rstrip('/')
    if verification:
        subject = 'Verify your CampusRipple email'
        body = ('Verify your CampusRipple account using this link (valid for 24 hours):\n\n'
                f'{base_url}{path}\n\nIf you did not create this account, you can ignore this email.')
    else:
        subject = 'Reset your CampusRipple password'
        body = ('A password reset was requested for your CampusRipple account.\n\n'
                f'Reset your password using this link (valid for 30 minutes): {base_url}{path}\n\n'
                'If you did not request this, you can ignore this email.')
    return send_custom_email(app, recipient, subject, body)


def send_custom_email(app, recipient, subject, body):
    """Send a plain-text email through configured SMTP; never log message contents."""
    if not app.config.get('MAIL_SERVER') or not app.config.get('MAIL_DEFAULT_SENDER'):
        app.logger.warning('Email requested but SMTP is not configured.')
        return False
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = app.config['MAIL_DEFAULT_SENDER']
    message['To'] = recipient
    message.set_content(body)
    try:
        use_ssl = bool(app.config.get('MAIL_USE_SSL', False))
        use_tls = bool(app.config.get('MAIL_USE_TLS', True))
        if use_ssl and use_tls:
            app.logger.error('SMTP configuration invalid: MAIL_USE_SSL and MAIL_USE_TLS cannot both be enabled.')
            return False
        timeout = int(app.config.get('MAIL_TIMEOUT', 10))
        if timeout < 1 or timeout > 120:
            app.logger.error('SMTP configuration invalid: MAIL_TIMEOUT must be between 1 and 120 seconds.')
            return False
        if use_ssl:
            with smtplib.SMTP_SSL(app.config['MAIL_SERVER'], int(app.config.get('MAIL_PORT', 465)), timeout=timeout) as smtp:
                username = app.config.get('MAIL_USERNAME')
                password = app.config.get('MAIL_PASSWORD')
                if username:
                    smtp.login(username, password or '')
                smtp.send_message(message)
        else:
            with smtplib.SMTP(app.config['MAIL_SERVER'], int(app.config.get('MAIL_PORT', 587)), timeout=timeout) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                username = app.config.get('MAIL_USERNAME')
                password = app.config.get('MAIL_PASSWORD')
                if username:
                    smtp.login(username, password or '')
                smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        app.logger.exception('Account email delivery failed.')
        return False


def send_smtp_test_email(app, recipient):
    return send_custom_email(app, recipient, 'CampusRipple SMTP configuration test',
        'This message confirms that CampusRipple can send email using the configured SMTP settings. No account action is required.')


def valid_clock(value):
    return (isinstance(value, str) and len(value) == 5 and value[2] == ':' and
            value[:2].isdigit() and value[3:].isdigit() and
            0 <= int(value[:2]) <= 23 and 0 <= int(value[3:]) <= 59)

def valid_iso_date(value):
    try:
        return len(value) == 10 and datetime.strptime(value, '%Y-%m-%d').date().isoformat() == value
    except (TypeError, ValueError):
        return False
