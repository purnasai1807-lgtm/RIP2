from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(24), nullable=False, default='student', index=True)
    reset_token_hash = db.Column(db.String(64), nullable=True, index=True)
    reset_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    email_verification_token_hash = db.Column(db.String(64), nullable=True, index=True)
    email_verification_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    scenarios = db.relationship('Scenario', backref='owner', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Scenario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    domain = db.Column(db.String(40), nullable=False, default='General')
    change_variable = db.Column(db.String(60), nullable=False)
    current_value = db.Column(db.String(120), nullable=False)
    proposed_value = db.Column(db.String(120), nullable=False)
    context = db.Column(db.Text, nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='Draft')
    approval_note = db.Column(db.String(1000), nullable=False, default='')
    analysis_version = db.Column(db.String(40), nullable=True)
    analyzed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    impacts = db.relationship('Impact', backref='scenario', cascade='all, delete-orphan', lazy=True, order_by='Impact.level, Impact.id')


class Impact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenario.id'), nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)
    activity = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cause = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(12), nullable=False, default='Medium')
    likelihood = db.Column(db.String(12), nullable=False, default='Medium')
    mitigation = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(120), nullable=False, default='rule-based hypothesis; verify against college records')
    parent_activity = db.Column(db.String(140), nullable=False, default='Proposed change')
    evidence_ref = db.Column(db.String(160), nullable=True)


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    academic_year = db.Column(db.String(20), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    department = db.relationship('Department', backref=db.backref('courses', lazy=True))


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    room_type = db.Column(db.String(24), nullable=False, default='Classroom')
    capacity = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False, index=True)
    faculty_name = db.Column(db.String(100), nullable=False)
    day_of_week = db.Column(db.String(12), nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    source_system = db.Column(db.String(40), nullable=False, default='manual')
    source_record_id = db.Column(db.String(100), nullable=True, index=True)
    source_synced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    course = db.relationship('Course', backref=db.backref('timetable_entries', lazy=True))
    room = db.relationship('Room', backref=db.backref('timetable_entries', lazy=True))


class AuditEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(500), nullable=False, default='')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user = db.relationship('User', backref=db.backref('audit_events', lazy=True))


class ExamSchedule(db.Model):
    """College examination schedule. Dates use ISO YYYY-MM-DD strings for portable forms."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    exam_date = db.Column(db.String(10), nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='Scheduled')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship('Course')
    room = db.relationship('Room')
    creator = db.relationship('User')


class CampusEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    event_date = db.Column(db.String(10), nullable=False, index=True)
    location = db.Column(db.String(140), nullable=False)
    organizer = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(1000), nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='Planned')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    creator = db.relationship('User')


class MaintenanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.String(2000), nullable=False)
    priority = db.Column(db.String(12), nullable=False, default='Medium')
    status = db.Column(db.String(20), nullable=False, default='Open', index=True)
    reported_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to = db.Column(db.String(100), nullable=False, default='')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    room = db.relationship('Room')
    reporter = db.relationship('User')


class AttendanceSession(db.Model):
    """An attendance window for a class or activity; self check-in is explicitly not identity proof."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True, index=True)
    session_date = db.Column(db.String(10), nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Open', index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship('Course')
    creator = db.relationship('User')


class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_session.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    marked_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='Unverified')
    verified_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    __table_args__ = (db.UniqueConstraint('session_id', 'user_id', name='uq_attendance_session_user'),)
    session = db.relationship('AttendanceSession', backref=db.backref('records', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', foreign_keys=[user_id])
    verifier = db.relationship('User', foreign_keys=[verified_by])


class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(60), nullable=False, default='General')
    location = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.String(3000), nullable=False)
    audience = db.Column(db.String(20), nullable=False, default='All')
    expires_on = db.Column(db.String(10), nullable=True, index=True)
    published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    creator = db.relationship('User')


class ServiceRequest(db.Model):
    """Student/staff grievance and service request with auditable status changes."""
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    category = db.Column(db.String(32), nullable=False, default='General')
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.String(3000), nullable=False)
    priority = db.Column(db.String(12), nullable=False, default='Medium')
    status = db.Column(db.String(20), nullable=False, default='Open', index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolution_note = db.Column(db.String(2000), nullable=False, default='')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    requester = db.relationship('User', foreign_keys=[requester_id])
    assignee = db.relationship('User', foreign_keys=[assigned_to])


class FacultySubstitution(db.Model):
    """Proposed substitute for a saved timetable session; never rewrites the source timetable."""
    id = db.Column(db.Integer, primary_key=True)
    timetable_entry_id = db.Column(db.Integer, db.ForeignKey('timetable_entry.id'), nullable=False, index=True)
    substitute_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    reason = db.Column(db.String(1000), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending', index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_note = db.Column(db.String(1000), nullable=False, default='')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    timetable_entry = db.relationship('TimetableEntry')
    substitute = db.relationship('User', foreign_keys=[substitute_user_id])
    requester = db.relationship('User', foreign_keys=[requested_by])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])


class InvigilatorAssignment(db.Model):
    """Exam invigilator allocation with unique assignment and clash checks in service logic."""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam_schedule.id'), nullable=False, index=True)
    faculty_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('exam_id', 'faculty_user_id', name='uq_exam_invigilator'),)
    exam = db.relationship('ExamSchedule', backref=db.backref('invigilators', lazy=True, cascade='all, delete-orphan'))
    faculty = db.relationship('User', foreign_keys=[faculty_user_id])
    assigner = db.relationship('User', foreign_keys=[assigned_by])


class AcademicCalendarItem(db.Model):
    """Academic calendar entries for holidays, deadlines, exams and important dates."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    item_type = db.Column(db.String(24), nullable=False, default='Deadline', index=True)
    start_date = db.Column(db.String(10), nullable=False, index=True)
    end_date = db.Column(db.String(10), nullable=True)
    audience = db.Column(db.String(20), nullable=False, default='All')
    details = db.Column(db.String(2000), nullable=False, default='')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    creator = db.relationship('User')


class InAppNotification(db.Model):
    """Persistent in-app notice scoped to one recipient."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    message = db.Column(db.String(1000), nullable=False)
    category = db.Column(db.String(32), nullable=False, default='General')
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user = db.relationship('User', backref=db.backref('notifications', lazy=True, cascade='all, delete-orphan'))


class LoginAttempt(db.Model):
    """Privacy-preserving persistent login throttling; raw identifiers are never stored."""
    id = db.Column(db.Integer, primary_key=True)
    email_digest = db.Column(db.String(64), nullable=False, index=True)
    ip_digest = db.Column(db.String(64), nullable=False, index=True)
    succeeded = db.Column(db.Boolean, nullable=False, default=False)
    attempted_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class IntegrationSyncRun(db.Model):
    """Auditable result of a read-only external-data fetch and local reconciliation."""
    id = db.Column(db.Integer, primary_key=True)
    integration = db.Column(db.String(40), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, index=True)
    records_received = db.Column(db.Integer, nullable=False, default=0)
    records_created = db.Column(db.Integer, nullable=False, default=0)
    records_updated = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.String(1000), nullable=False, default='')
    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)


class ImpactFeedback(db.Model):
    """Human review of an impact prediction, for auditable quality evaluation."""
    id = db.Column(db.Integer, primary_key=True)
    impact_id = db.Column(db.Integer, db.ForeignKey('impact.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    assessment = db.Column(db.String(20), nullable=False, index=True)  # Confirmed, Incorrect, Uncertain
    observed_outcome = db.Column(db.String(1200), nullable=False, default='')
    analysis_version = db.Column(db.String(40), nullable=False, default='unknown')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    impact = db.relationship('Impact', backref=db.backref('feedback', cascade='all, delete-orphan', lazy=True))
    user = db.relationship('User', backref=db.backref('impact_feedback', cascade='all, delete-orphan', lazy=True))
    __table_args__ = (db.UniqueConstraint('impact_id', 'user_id', name='uq_impact_feedback_user'),)
