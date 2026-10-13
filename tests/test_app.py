import pytest
from app import create_app, db
from app.models import User, Scenario, Impact, Department
from app.engine import analyze

@pytest.fixture()
def app():
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key-that-is-long-enough',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
    })
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

def get_csrf(client, path='/register'):
    response = client.get(path)
    assert response.status_code == 200
    with client.session_transaction() as sess:
        return sess['_csrf_token']

def register(client, email='student@aceec.ac.in', password='correct-horse-battery'):
    token = get_csrf(client)
    return client.post('/register', data={
        '_csrf_token': token, 'name': 'Student', 'email': email, 'password': password
    }, follow_redirects=True)

def test_register_and_dashboard(client):
    response = register(client)
    assert response.status_code == 200
    assert b'Your decisions' in response.data


def test_registration_rejects_non_aceec_email(client):
    response = register(client, email='student@gmail.com')
    assert b'Only members of ACE Engineering College are eligible to register.' in response.data
    with client.application.app_context():
        assert User.query.filter_by(email='student@gmail.com').first() is None

def test_email_domain_allowlist_cannot_be_overridden(app, client):
    app.config['INSTITUTIONAL_EMAIL_DOMAINS'] = ('example.com', 'aceec.ac.in')
    response = register(client, email='student@example.com')
    assert b'Only members of ACE Engineering College are eligible to register.' in response.data
    with app.app_context():
        assert User.query.filter_by(email='student@example.com').first() is None

def test_login_page_does_not_display_registration_eligibility_policy(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Only members of ACE Engineering College are eligible to register.' not in response.data
    assert b'@aceec.ac.in' not in response.data


def test_registration_rejects_short_password(client):
    token = get_csrf(client)
    response = client.post('/register', data={
        '_csrf_token': token, 'name': 'Student', 'email': 'a@aceec.ac.in', 'password': 'short'
    }, follow_redirects=True)
    assert b'at least 12 characters' in response.data

def test_impact_engine_has_two_downstream_levels():
    impacts = analyze('Education', 'Time', '10 AM', '12 PM', 'Room is shared')
    assert any(item['level'] == 1 for item in impacts)
    assert any(item['level'] == 2 for item in impacts)
    assert any(item['level'] >= 3 for item in impacts)
    assert all(item['mitigation'] and item['cause'] for item in impacts)
    assert all(item.get('parent_activity') for item in impacts)
    assert all('hypothesis' in item['source'].lower() for item in impacts if item['level'] > 1 and 'college database evidence' not in item['source'].lower())
    assert any(item['level'] == 3 and item['parent_activity'] for item in impacts)

def test_private_scenario_cannot_be_viewed_by_other_user(app, client):
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=owner.id, title='Private plan', domain='General', change_variable='Time', current_value='10', proposed_value='11', context='')
        db.session.add(scenario)
        db.session.commit()
        scenario_id = scenario.id
    with client.session_transaction() as sess:
        sess.clear()
    response = client.get(f'/scenarios/{scenario_id}')
    assert response.status_code in (302, 401)

def test_missing_csrf_token_rejected(client):
    response = client.post('/register', data={'name': 'A', 'email': 'a@aceec.ac.in', 'password': 'correct-horse-battery'})
    assert response.status_code == 400

def test_csv_import_creates_private_draft_scenarios(client):
    import io
    register(client)
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    payload = ('title,domain,change_variable,current_value,proposed_value,context\n'
               'Move lab,Timetable & classrooms,Time,10 AM,12 PM,Check room availability\n').encode()
    response = client.post('/imports', data={
        '_csrf_token': token,
        'file': (io.BytesIO(payload), 'college.csv')
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b'Imported 1 college decision scenarios' in response.data
    with client.application.app_context():
        scenario = Scenario.query.filter_by(title='Move lab').first()
        assert scenario is not None
        assert scenario.status == 'Draft'

def test_csv_import_rejects_invalid_row_without_partial_save(client):
    import io
    register(client)
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    payload = ('title,domain,change_variable,current_value,proposed_value,context\n'
               'Good row,Timetable & classrooms,Time,10 AM,12 PM,ok\n'
               'Bad row,Invalid domain,Time,10 AM,12 PM,not ok\n').encode()
    response = client.post('/imports', data={
        '_csrf_token': token,
        'file': (io.BytesIO(payload), 'college.csv')
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b'Row 3: Choose a valid domain.' in response.data
    with client.application.app_context():
        assert Scenario.query.count() == 0

def test_admin_route_denied_to_student(client):
    register(client)
    response = client.get('/admin/users')
    assert response.status_code == 403

def test_password_reset_uses_generic_response_and_single_use_token(app, client, monkeypatch):
    import re
    from app import routes

    register(client)
    sent = {}

    def fake_send(app_obj, recipient, reset_path):
        sent['recipient'] = recipient
        sent['path'] = reset_path
        return True

    monkeypatch.setattr(routes, 'send_password_reset_email', fake_send)
    token = get_csrf(client, '/forgot-password')
    response = client.post('/forgot-password', data={
        '_csrf_token': token, 'email': 'student@aceec.ac.in'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'If an account matches that email' in response.data
    assert sent['recipient'] == 'student@aceec.ac.in'
    match = re.search(r'/reset-password/([^\s]+)', sent['path'])
    assert match
    reset_token = match.group(1)

    token = get_csrf(client, sent['path'])
    response = client.post(sent['path'], data={
        '_csrf_token': token,
        'password': 'new-secure-password-2026',
        'confirm_password': 'new-secure-password-2026',
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='student@aceec.ac.in').first()
        assert user.check_password('new-secure-password-2026')
        assert user.reset_token_hash is None
        assert user.reset_token_expires_at is None

    response = client.get(f'/reset-password/{reset_token}')
    assert response.status_code == 400


def test_password_reset_rejects_mismatched_passwords(app, client, monkeypatch):
    import re
    from app import routes

    register(client)
    sent = {}
    monkeypatch.setattr(routes, 'send_password_reset_email', lambda app_obj, recipient, path: sent.update(path=path) or True)
    csrf = get_csrf(client, '/forgot-password')
    client.post('/forgot-password', data={'_csrf_token': csrf, 'email': 'student@aceec.ac.in'})
    path = sent['path']
    csrf = get_csrf(client, path)
    response = client.post(path, data={
        '_csrf_token': csrf,
        'password': 'new-secure-password-2026',
        'confirm_password': 'different-secure-password',
    }, follow_redirects=True)
    assert b'passwords do not match' in response.data.lower()
    with app.app_context():
        user = User.query.filter_by(email='student@aceec.ac.in').first()
        assert user.check_password('correct-horse-battery')

def create_admin(app):
    with app.app_context():
        admin = User(name='Coordinator', email='coordinator@aceec.ac.in', role='coordinator')
        admin.set_password('coordinator-password-2026')
        db.session.add(admin)
        db.session.commit()
        return admin.id


def test_student_cannot_add_shared_college_records(app, client):
    register(client)
    token = get_csrf(client, '/college-workspace')
    response = client.post('/college-workspace/departments', data={
        '_csrf_token': token, 'code': 'CSD', 'name': 'Computer Science and Design'
    })
    assert response.status_code == 403
    with app.app_context():
        from app.models import Department
        assert Department.query.count() == 0


def test_coordinator_can_add_department_and_audit_event(app, client):
    admin_id = create_admin(app)
    token = get_csrf(client, '/login')
    client.post('/login', data={'_csrf_token': token, 'email': 'coordinator@aceec.ac.in',
                                'password': 'coordinator-password-2026'})
    token = get_csrf(client, '/college-workspace')
    response = client.post('/college-workspace/departments', data={
        '_csrf_token': token, 'code': 'CSD', 'name': 'Computer Science and Design'
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        from app.models import Department, AuditEvent
        assert Department.query.filter_by(code='CSD').first() is not None
        assert AuditEvent.query.filter_by(action='department.created').count() == 1


def test_timetable_rejects_room_overlap(app, client):
    from app.models import Department, Course, Room, TimetableEntry
    coordinator_id = create_admin(app)
    with app.app_context():
        department = Department(code='CSD', name='Computer Science and Design')
        db.session.add(department); db.session.flush()
        course = Course(code='CSD-1', name='First Year', department_id=department.id, academic_year='2026-27', semester='1')
        room = Room(code='LAB-1', name='Programming Lab', room_type='Lab', capacity=60)
        db.session.add_all([course, room]); db.session.flush()
        db.session.add(TimetableEntry(course_id=course.id, room_id=room.id, faculty_name='Faculty One',
            day_of_week='Monday', start_time='09:00', end_time='10:00', subject='Programming'))
        db.session.commit()
        course_id, room_id = course.id, room.id
    token = get_csrf(client, '/login')
    client.post('/login', data={'_csrf_token': token, 'email': 'coordinator@aceec.ac.in',
                                'password': 'coordinator-password-2026'})
    token = get_csrf(client, '/college-workspace')
    response = client.post('/college-workspace/timetable', data={
        '_csrf_token': token, 'course_id': course_id, 'room_id': room_id,
        'faculty_name': 'Faculty Two', 'day_of_week': 'Monday', 'start_time': '09:30',
        'end_time': '10:30', 'subject': 'Data Structures'
    }, follow_redirects=True)
    assert b'Room conflict' in response.data
    with app.app_context():
        assert TimetableEntry.query.count() == 1

def test_public_registration_cannot_grant_admin_role(app, client, monkeypatch):
    # A known email address must never be sufficient to self-assign administrator privileges.
    monkeypatch.setenv('ADMIN_EMAIL', 'student@aceec.ac.in')
    response = register(client, email='student@aceec.ac.in')
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='student@aceec.ac.in').first()
        assert user is not None
        assert user.role == 'student'

def test_admin_cli_can_promote_existing_user(app, client):
    register(client, email='admin-candidate@aceec.ac.in')
    runner = app.test_cli_runner()
    result = runner.invoke(args=['create-admin', 'admin-candidate@aceec.ac.in'])
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = User.query.filter_by(email='admin-candidate@aceec.ac.in').first()
        assert user.role == 'admin'


def test_operations_page_requires_login(client):
    response = client.get('/college-operations')
    assert response.status_code in (302, 401)


def test_student_can_report_maintenance_but_cannot_change_status(app, client):
    from app.models import Room, MaintenanceRequest
    register(client)
    with app.app_context():
        room = Room(code='LAB-2', name='Design Lab', room_type='Lab', capacity=40)
        db.session.add(room)
        db.session.commit()
        room_id = room.id
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    response = client.post('/college-operations', data={
        '_csrf_token': token, 'kind': 'maintenance', 'room_id': room_id,
        'title': 'Projector broken', 'details': 'Projector does not power on', 'priority': 'High'
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        item = MaintenanceRequest.query.first()
        assert item is not None and item.status == 'Open'
        item_id = item.id
    response = client.post(f'/college-operations/maintenance/{item_id}/status', data={
        '_csrf_token': token, 'status': 'Resolved'
    })
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(MaintenanceRequest, item_id).status == 'Open'


def test_coordinator_can_add_exam_and_reject_hall_overlap(app, client):
    from app.models import Department, Course, Room, ExamSchedule
    create_admin(app)
    with app.app_context():
        department = Department(code='ECE', name='Electronics and Communication')
        db.session.add(department)
        db.session.flush()
        course = Course(code='ECE-1', name='First Year ECE', department_id=department.id, academic_year='2026-27', semester='1')
        room = Room(code='HALL-1', name='Exam Hall 1', room_type='Hall', capacity=100)
        db.session.add_all([course, room])
        db.session.commit()
        course_id, room_id = course.id, room.id
    token = get_csrf(client, '/login')
    client.post('/login', data={'_csrf_token': token, 'email': 'coordinator@aceec.ac.in', 'password': 'coordinator-password-2026'})
    token = get_csrf(client, '/college-operations')
    data = {'_csrf_token': token, 'kind': 'exam', 'title': 'Midterm', 'event_date': '2026-11-02',
            'start_time': '09:00', 'end_time': '10:00', 'course_id': course_id, 'room_id': room_id}
    response = client.post('/college-operations', data=data, follow_redirects=True)
    assert b'Exam schedule added' in response.data
    response = client.post('/college-operations', data={**data, 'title': 'Another exam', 'start_time': '09:30', 'end_time': '10:30'}, follow_redirects=True)
    assert b'Exam hall conflict' in response.data
    with app.app_context():
        assert ExamSchedule.query.count() == 1


def test_student_can_check_in_only_once_per_attendance_session(app, client):
    from app.models import AttendanceSession, AttendanceRecord
    register(client)
    with app.app_context():
        admin = User(email='faculty@aceec.ac.in', name='Faculty', role='faculty')
        admin.set_password('faculty-password-2026')
        db.session.add(admin)
        db.session.flush()
        session = AttendanceSession(title='Python Lab', session_date='2026-11-02', start_time='09:00', end_time='10:00', created_by=admin.id)
        db.session.add(session)
        db.session.commit()
        session_id = session.id
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    payload = {'_csrf_token': token, 'kind': 'attendance_checkin', 'session_id': session_id}
    first = client.post('/campus-services', data=payload, follow_redirects=True)
    assert b'Check-in recorded' in first.data
    second = client.post('/campus-services', data=payload, follow_redirects=True)
    assert b'already checked in' in second.data
    with app.app_context():
        assert AttendanceRecord.query.filter_by(session_id=session_id).count() == 1


def test_student_cannot_create_inventory_or_announcement(client):
    register(client)
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    for kind in ('inventory', 'announcement'):
        response = client.post('/campus-services', data={'_csrf_token': token, 'kind': kind}, follow_redirects=False)
        assert response.status_code == 403


def test_inventory_adjustment_cannot_make_stock_negative(app, client):
    from app.models import InventoryItem
    with app.app_context():
        admin = User(email='admin@aceec.ac.in', name='Admin', role='admin')
        admin.set_password('admin-password-2026')
        db.session.add(admin)
        db.session.flush()
        item = InventoryItem(item_code='HDMI-1', name='HDMI cable', category='AV', location='Lab 1', quantity=2, reorder_level=1)
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    token = get_csrf(client, '/login')
    client.post('/login', data={'_csrf_token': token, 'email': 'admin@aceec.ac.in', 'password': 'admin-password-2026'})
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    response = client.post('/campus-services', data={'_csrf_token': token, 'kind': 'inventory_adjust', 'item_id': item_id, 'delta': -3, 'note': 'bad adjustment'}, follow_redirects=True)
    assert b'quantity cannot become negative' in response.data
    with app.app_context():
        assert db.session.get(InventoryItem, item_id).quantity == 2

def test_impact_engine_includes_database_evidence_as_separate_source():
    evidence = [{
        'level': 1,
        'activity': 'Room already booked',
        'description': 'LAB-1 is used from 10:00 to 11:00.',
        'cause': 'The room record matches the proposed resource.',
        'severity': 'High',
        'likelihood': 'High',
        'mitigation': 'Choose a free room or reschedule the existing booking.',
        'source': 'college database evidence',
    }]
    impacts = analyze('Timetable & classrooms', 'Resource', 'LAB-2', 'LAB-1', 'move lab', evidence)
    assert any(i['activity'] == 'Room already booked' and i['source'] == 'college database evidence' for i in impacts)
    assert all(i['cause'] and i['mitigation'] for i in impacts)
    assert {i['level'] for i in impacts}.issuperset({1, 2, 3})


def test_simulation_renders_alternative_without_overwriting_saved_proposal(app, client):
    register(client)
    with app.app_context():
        user = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=user.id, title='Move lab', domain='Timetable & classrooms',
                            change_variable='Time', current_value='10:00', proposed_value='12:00', context='CSD lab')
        db.session.add(scenario)
        db.session.commit()
        scenario_id = scenario.id
    token = get_csrf(client, f'/scenarios/{scenario_id}')
    response = client.post(f'/scenarios/{scenario_id}/simulate', data={
        '_csrf_token': token, 'alternative_value': '11:00'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'11:00' in response.data
    assert b'PRACTICAL NEXT STEP' in response.data
    with app.app_context():
        scenario = db.session.get(Scenario, scenario_id)
        assert scenario.proposed_value == '12:00'

def test_student_checkin_stays_unverified_until_staff_action(app, client):
    from app.models import Course, Department, AttendanceSession, AttendanceRecord
    register(client)
    with app.app_context():
        student = User.query.filter_by(email='student@aceec.ac.in').first()
        dept = Department(code='CSD', name='Computer Science and Design')
        db.session.add(dept); db.session.flush()
        course = Course(code='CSD-1', name='First Year', department_id=dept.id, academic_year='2026-27', semester='1')
        db.session.add(course); db.session.flush()
        session_row = AttendanceSession(title='Programming', course_id=course.id, session_date='2026-10-11', start_time='09:00', end_time='10:00', created_by=student.id)
        db.session.add(session_row); db.session.commit()
        session_id = session_row.id
    token = get_csrf(client, '/campus-services')
    response = client.post('/campus-services', data={
        '_csrf_token': token, 'kind': 'attendance_checkin', 'session_id': session_id
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        record = AttendanceRecord.query.filter_by(session_id=session_id).one()
        assert record.status == 'Unverified'
        assert record.verified_by is None


def test_health_endpoint_does_not_require_login(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'


def test_academic_services_page_and_student_service_request(client):
    register(client)
    response = client.get('/academic-services')
    assert response.status_code == 200
    assert b'Academic calendar' in response.data
    token = get_csrf(client, '/academic-services')
    response = client.post('/academic-services', data={
        '_csrf_token': token,
        'kind': 'service_request',
        'title': 'Projector is not working',
        'description': 'The projector in the lab does not turn on.',
        'category': 'Facilities',
        'priority': 'Medium',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Projector is not working' in response.data
    with client.application.app_context():
        from app.models import ServiceRequest
        item = ServiceRequest.query.filter_by(title='Projector is not working').first()
        assert item is not None and item.status == 'Open'


def test_student_cannot_publish_academic_calendar_item(app, client):
    register(client)
    token = get_csrf(client, '/academic-services')
    response = client.post('/academic-services', data={
        '_csrf_token': token,
        'kind': 'calendar_item',
        'title': 'Fake holiday',
        'item_type': 'Holiday',
        'start_date': '2026-12-25',
        'end_date': '',
        'audience': 'All',
        'details': 'Unauthorized calendar change',
    })
    assert response.status_code == 403
    with client.application.app_context():
        from app.models import AcademicCalendarItem
        assert AcademicCalendarItem.query.count() == 0


def test_reports_and_compare_pages_load_for_signed_in_student(client):
    register(client)
    assert client.get('/reports').status_code == 200
    assert client.get('/scenarios/compare').status_code == 200
    assert client.get('/reports/impact-summary.csv').status_code == 200


def test_security_headers_are_present(client):
    response = client.get('/')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'DENY'
    assert response.headers.get('Permissions-Policy') == 'camera=(), microphone=(), geolocation=()'
    assert response.headers.get('Content-Security-Policy')


def test_production_requires_secure_session_cookie():
    with pytest.raises(RuntimeError, match='COOKIE_SECURE=true'):
        create_app({
            'TESTING': True,
            'APP_ENV': 'production',
            'SECRET_KEY': 'test-secret-key-that-is-long-enough-for-production',
            'SESSION_COOKIE_SECURE': False,
        })


def test_hsts_only_enabled_for_secure_cookie_configuration(app):
    # Test configuration uses HTTP/in-memory SQLite, so HSTS must not be advertised.
    response = app.test_client().get('/')
    assert 'Strict-Transport-Security' not in response.headers


def test_evidence_items_without_parent_do_not_crash_and_get_causal_parent():
    evidence = [
        {'level': 1, 'activity': 'Observed room booking', 'description': 'Room is booked.',
         'cause': 'The room appears in timetable records.', 'mitigation': 'Choose a free room.',
         'source': 'college database evidence'},
        {'level': 2, 'activity': 'Dependent lab disruption', 'description': 'A lab may move.',
         'cause': 'The lab depends on the room.', 'mitigation': 'Reserve an alternate lab.',
         'source': 'dependency analysis'},
    ]
    impacts = analyze('Timetable & classrooms', 'Resource', 'Room A', 'Room B', evidence=evidence)
    evidence_impacts = [item for item in impacts if item['activity'] in {'Observed room booking', 'Dependent lab disruption'}]
    assert len(evidence_impacts) == 2
    level_one = next(item for item in evidence_impacts if item['level'] == 1)
    level_two = next(item for item in evidence_impacts if item['level'] == 2)
    assert level_one['parent_activity'] == 'Proposed change'
    assert level_two['parent_activity'] in {item['activity'] for item in impacts if item['level'] == 1}
    assert level_two['cause']
    assert level_two['mitigation']


def test_login_throttles_repeated_failed_attempts(client):
    csrf = get_csrf(client, '/login')
    for _ in range(8):
        response = client.post('/login', data={
            '_csrf_token': csrf, 'email': 'unknown@aceec.ac.in', 'password': 'incorrect-password'
        })
        assert response.status_code == 200
    response = client.post('/login', data={
        '_csrf_token': csrf, 'email': 'unknown@aceec.ac.in', 'password': 'incorrect-password'
    })
    assert response.status_code == 429
    assert b'Too many sign-in attempts' in response.data


def test_json_export_contains_traceable_impact_chain(client, app):
    import json
    register(client)
    csrf = get_csrf(client, '/scenarios/new')
    response = client.post('/scenarios/new', data={
        '_csrf_token': csrf, 'title': 'Move lab', 'domain': 'Timetable & classrooms',
        'change_variable': 'Time', 'current_value': '10:00', 'proposed_value': '12:00',
        'context': 'Shared room and faculty'
    }, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers['Location']
    scenario_id = int(location.rstrip('/').split('/')[-1])
    csrf = get_csrf(client, location)
    client.post(f'/scenarios/{scenario_id}/analyze', data={'_csrf_token': csrf})
    response = client.get(f'/scenarios/{scenario_id}/export.json')
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload['schema_version'] == '1.0'
    assert payload['summary']['direct_impacts'] >= 1
    assert any(item['level'] == 3 and item['mitigation'] for item in payload['impacts'])


def test_email_verification_required_before_login(app, client, monkeypatch):
    from app import routes
    app.config['REQUIRE_EMAIL_VERIFICATION'] = True
    sent = {}
    def fake_send(app_obj, recipient, path, verification=False):
        sent.update(recipient=recipient, path=path, verification=verification)
        return True
    monkeypatch.setattr(routes, 'send_account_email', fake_send)
    response = register(client, email='verify@aceec.ac.in')
    assert response.status_code == 200
    assert sent['verification'] is True
    assert sent['recipient'] == 'verify@aceec.ac.in'
    with app.app_context():
        user = User.query.filter_by(email='verify@aceec.ac.in').first()
        assert user is not None and user.email_verified_at is None
    csrf = get_csrf(client, '/login')
    response = client.post('/login', data={'_csrf_token': csrf, 'email': 'verify@aceec.ac.in',
                                           'password': 'correct-horse-battery'}, follow_redirects=True)
    assert b'verify your email' in response.data.lower()
    response = client.get(sent['path'], follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='verify@aceec.ac.in').first()
        assert user.email_verified_at is not None


def test_official_data_adapter_fails_closed_without_authorized_credentials():
    from app.integrations.college_source import fetch_timetable, CollegeSourceError
    class FakeApp:
        config = {'COLLEGE_DATA_API_URL': '', 'COLLEGE_DATA_API_TOKEN': ''}
    with pytest.raises(CollegeSourceError, match='not configured'):
        fetch_timetable(FakeApp())


def test_analysis_persists_rule_version_timestamp_and_json_provenance(app, client):
    import json
    from app.engine import RULE_VERSION
    register(client)
    with app.app_context():
        user = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=user.id, title='Traceable decision', domain='Timetable & classrooms',
            change_variable='Time', current_value='10:00', proposed_value='12:00', context='Synthetic test')
        db.session.add(scenario)
        db.session.commit()
        scenario_id = scenario.id
    csrf = get_csrf(client, f'/scenarios/{scenario_id}')
    response = client.post(f'/scenarios/{scenario_id}/analyze', data={'_csrf_token': csrf}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        scenario = db.session.get(Scenario, scenario_id)
        assert scenario.analysis_version == RULE_VERSION
        assert scenario.analyzed_at is not None
        assert all(hasattr(impact, 'evidence_ref') for impact in scenario.impacts)
    response = client.get(f'/scenarios/{scenario_id}/export.json')
    payload = json.loads(response.data)
    assert payload['scenario']['analysis_version'] == RULE_VERSION
    assert payload['scenario']['analyzed_at']
    assert all('evidence_ref' in item for item in payload['impacts'])


def test_institutional_email_domain_allowlist_is_enforced(app, client):
    app.config['INSTITUTIONAL_EMAIL_DOMAINS'] = ('students.college.example',)
    csrf = get_csrf(client, '/register')
    response = client.post('/register', data={'_csrf_token': csrf, 'name': 'Student',
        'email': 'student@gmail.com', 'password': 'correct-horse-battery'}, follow_redirects=True)
    assert b'institution-approved domain' in response.data.lower()
    with app.app_context():
        assert User.query.filter_by(email='student@gmail.com').first() is None


def test_official_data_adapter_validates_and_normalizes_timetable(monkeypatch):
    import json
    from app.integrations import college_source
    row = {
        'record_id': 'row-1', 'department_code': 'CSD', 'department_name': 'Computing',
        'course_code': 'CSD-101', 'course_name': 'Computing Basics', 'academic_year': '2026-27',
        'semester': '1', 'room_code': 'LAB-1', 'room_name': 'Lab One', 'room_type': 'Lab',
        'capacity': 40, 'faculty_name': 'Faculty One', 'day_of_week': 'monday',
        'start_time': '09:00', 'end_time': '10:00', 'subject': 'Python'
    }
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size): return json.dumps({'timetable': [row]}).encode()
    monkeypatch.setattr(college_source.urllib.request, 'urlopen', lambda *args, **kwargs: FakeResponse())
    class FakeApp:
        config = {'COLLEGE_DATA_API_URL': 'https://college.example/api/timetable',
                  'COLLEGE_DATA_API_TOKEN': 'test-only-token', 'COLLEGE_DATA_API_TIMEOUT': 1}
    result = college_source.fetch_timetable(FakeApp())
    assert len(result) == 1
    assert result[0]['day_of_week'] == 'Monday'
    assert result[0]['capacity'] == 40


def test_impact_feedback_is_saved_and_visible_to_admin(app, client):
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=owner.id, title='Shift lab', domain='Timetable & classrooms',
                            change_variable='Time', current_value='10 AM', proposed_value='12 PM',
                            context='', status='Analyzed', analysis_version='rules-test-v1')
        db.session.add(scenario)
        db.session.flush()
        impact = Impact(scenario_id=scenario.id, level=1, activity='Room conflict',
                         description='A room may conflict.', cause='The room is shared.',
                         severity='High', likelihood='Medium', mitigation='Choose another room.',
                         source='rule-based hypothesis', parent_activity='Proposed change')
        db.session.add(impact)
        db.session.commit()
        impact_id = impact.id
        scenario_id = scenario.id
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    response = client.post(f'/impacts/{impact_id}/feedback', data={
        '_csrf_token': token, 'assessment': 'Confirmed', 'observed_outcome': 'Room booking showed overlap.'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'impact review has been recorded' in response.data
    with app.app_context():
        from app.models import ImpactFeedback
        feedback = ImpactFeedback.query.filter_by(impact_id=impact_id).one()
        assert feedback.assessment == 'Confirmed'
        assert feedback.analysis_version == 'rules-test-v1'
        feedback_user = User.query.filter_by(email='student@aceec.ac.in').first()
        feedback_user.role = 'admin'
        db.session.commit()
    response = client.get('/admin/impact-quality')
    assert response.status_code == 200
    assert b'Room conflict' in response.data
    assert b'Confirmed' in response.data


def test_impact_feedback_rejects_invalid_assessment(app, client):
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=owner.id, title='Shift lab', domain='General',
                            change_variable='Time', current_value='10 AM', proposed_value='12 PM', context='')
        db.session.add(scenario)
        db.session.flush()
        impact = Impact(scenario_id=scenario.id, level=1, activity='Conflict', description='Conflict',
                         cause='Cause', severity='Medium', likelihood='Medium', mitigation='Mitigate',
                         source='rule-based hypothesis', parent_activity='Proposed change')
        db.session.add(impact)
        db.session.commit()
        impact_id = impact.id
    with client.session_transaction() as sess:
        token = sess['_csrf_token']
    response = client.post(f'/impacts/{impact_id}/feedback', data={
        '_csrf_token': token, 'assessment': 'Definitely true', 'observed_outcome': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        from app.models import ImpactFeedback
        assert ImpactFeedback.query.count() == 0


def test_evidence_time_parser_rejects_ambiguous_and_detects_overlap():
    from app.evidence import parse_interval, overlaps
    assert parse_interval('10:00-11:00') == (600, 660)
    assert parse_interval('12:30') == (750, 810)
    assert overlaps(parse_interval('10:00-11:00'), parse_interval('10:45-11:30'))
    assert not overlaps(parse_interval('10:00-11:00'), parse_interval('11:00-12:00'))
    assert parse_interval('tomorrow morning') is None


def test_impact_comparison_reports_resolved_remaining_and_new_items():
    from app.evidence import compare_impacts
    baseline = [
        {'level': 1, 'activity': 'Room clash', 'evidence_ref': 'timetable_entry:2'},
        {'level': 2, 'activity': 'Lab delay', 'evidence_ref': None},
    ]
    alternative = [
        {'level': 2, 'activity': 'Lab delay', 'evidence_ref': None},
        {'level': 1, 'activity': 'Faculty clash', 'evidence_ref': 'timetable_entry:8'},
    ]
    result = compare_impacts(baseline, alternative)
    assert [x['activity'] for x in result['resolved']] == ['Room clash']
    assert [x['activity'] for x in result['remaining']] == ['Lab delay']
    assert [x['activity'] for x in result['new']] == ['Faculty clash']


def test_time_evidence_reports_insufficient_data_instead_of_claiming_conflict(app):
    from app.routes import collect_impact_evidence
    with app.app_context():
        evidence = collect_impact_evidence('Timetable & classrooms', 'Time', '10:00', '12:00', '')
        assert any(item['source'] == 'insufficient data' for item in evidence)
        assert not any(item['source'] == 'college database evidence' for item in evidence)


def test_resource_change_reports_exact_overlapping_room_record(app):
    from app.routes import collect_impact_evidence
    from app.models import Department, Course, Room, TimetableEntry
    with app.app_context():
        department = Department(code='CSD', name='Computer Science')
        db.session.add(department)
        db.session.flush()
        course = Course(code='CSD101', name='Intro Computing', department_id=department.id,
                        academic_year='2026', semester='1')
        room = Room(code='LAB-1', name='Lab One', room_type='Laboratory', capacity=40, is_active=True)
        db.session.add_all([course, room])
        db.session.flush()
        db.session.add(TimetableEntry(course_id=course.id, room_id=room.id, faculty_name='Dr Example',
                                      day_of_week='Monday', start_time='10:00', end_time='11:00',
                                      subject='Computing Lab', source_system='manual'))
        db.session.commit()
        evidence = collect_impact_evidence('Timetable & classrooms', 'Resource', 'LAB-2', 'LAB-1',
                                           'Monday 10:00-11:00')
        conflicts = [item for item in evidence if item['source'] == 'college database evidence']
        assert any(item['evidence_ref'].startswith('timetable_entry:') for item in conflicts)
        assert any('overlaps' in item['description'] for item in conflicts)


def test_liveness_and_security_headers(client):
    response = client.get('/livez')
    assert response.status_code == 200
    assert response.json == {'status': 'alive'}
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert response.headers['Permissions-Policy'] == 'camera=(), microphone=(), geolocation=()'


def test_json_analysis_api_returns_explainable_multilevel_impacts(client):
    register(client)
    with client.session_transaction() as sess:
        csrf = sess['_csrf_token']
    response = client.post('/api/v1/analyze', json={
        'domain': 'Timetable & classrooms',
        'variable': 'Time',
        'current_value': '10:00',
        'proposed_value': '12:00',
        'context': 'Monday, 10:00-11:00, CSD-2-1',
    }, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'analysis_complete'
    assert data['summary']['by_level']['1'] >= 1
    assert data['summary']['by_level']['2'] >= 1
    assert data['summary']['by_level']['3'] >= 1
    assert all(item['cause'] and item['mitigation'] for item in data['impacts'])
    assert data['mutates_saved_scenarios'] is False


def test_json_analysis_api_rejects_invalid_domain(client):
    register(client)
    with client.session_transaction() as sess:
        csrf = sess['_csrf_token']
    response = client.post('/api/v1/analyze', json={
        'domain': 'made-up domain', 'variable': 'Time',
        'current_value': '10:00', 'proposed_value': '12:00',
    }, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_json_compare_api_returns_mitigating_alternative_without_saving(client):
    register(client)
    with client.session_transaction() as sess:
        csrf = sess['_csrf_token']
    response = client.post('/api/v1/compare', json={
        'domain': 'Exams & academics', 'variable': 'Date',
        'current_value': '2026-11-02', 'proposed_value': '2026-11-05',
        'alternative_value': '2026-11-06', 'context': 'Exam calendar review',
    }, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    data = response.get_json()
    assert data['recommendation']
    assert 'resolved' in data['comparison']
    assert 'remaining' in data['comparison']
    assert 'new' in data['comparison']
    assert data['mutates_saved_scenarios'] is False


def test_api_metadata_requires_authentication(client):
    response = client.get('/api/v1/meta')
    assert response.status_code in (302, 401, 403)
    register(client)
    response = client.get('/api/v1/meta')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['api_version'] == 'v1'
    assert payload['domains']
    assert payload['variables']
    assert payload['write_requests_require_csrf'] is True


def test_api_scenarios_are_paginated_and_private(app, client):
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        own = Scenario(user_id=owner.id, title='Own scenario', domain='General',
                       change_variable='Time', current_value='10:00', proposed_value='11:00', context='test')
        other = User(name='Other', email='other@aceec.ac.in')
        other.set_password('other-password-2026')
        db.session.add(other)
        db.session.flush()
        private = Scenario(user_id=other.id, title='Private scenario', domain='General',
                           change_variable='Date', current_value='2026-10-12', proposed_value='2026-10-13', context='private')
        db.session.add_all([own, private])
        db.session.commit()
        own_id = own.id
        private_id = private.id
    response = client.get('/api/v1/scenarios?per_page=1&page=1')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['pagination']['total'] == 1
    assert len(payload['items']) == 1
    assert payload['items'][0]['title'] == 'Own scenario'
    assert client.get(f'/api/v1/scenarios/{own_id}').status_code == 200
    assert client.get(f'/api/v1/scenarios/{private_id}').status_code == 404


def test_api_scenario_detail_serializes_impact_chain(app, client):
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=owner.id, title='Impact chain', domain='General',
                            change_variable='Time', current_value='10:00', proposed_value='11:00', context='')
        db.session.add(scenario)
        db.session.flush()
        impact = Impact(scenario_id=scenario.id, level=1, activity='Direct impact',
                        description='Possible effect', cause='Because of the proposed change',
                        severity='Medium', likelihood='Medium', mitigation='Review the timetable',
                        source='rule-based hypothesis; verify against college records', parent_activity='Proposed change')
        db.session.add(impact)
        db.session.commit()
        scenario_id = scenario.id
    response = client.get(f'/api/v1/scenarios/{scenario_id}')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['impact_count'] == 1
    assert payload['impacts'][0]['activity'] == 'Direct impact'
    assert payload['impacts'][0]['mitigation'] == 'Review the timetable'


def test_api_rejects_invalid_pagination(client):
    register(client)
    response = client.get('/api/v1/scenarios?page=abc')
    assert response.status_code == 400
    assert response.get_json()['error']


def test_create_admin_cli_rejects_non_aceec_domain(app):
    result = app.test_cli_runner().invoke(args=['create-admin', 'admin@gmail.com'])
    assert result.exit_code != 0
    assert 'must use an eligible @aceec.ac.in email address' in result.output
    with app.app_context():
        assert User.query.filter_by(email='admin@gmail.com').first() is None


def test_reset_password_rejects_legacy_non_aceec_account(app, client):
    import hashlib
    from datetime import datetime, timedelta, timezone

    token = 'legacy-reset-token'
    with app.app_context():
        legacy = User(name='Legacy User', email='legacy@gmail.com')
        legacy.set_password('correct-horse-battery')
        legacy.reset_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        legacy.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=20)
        db.session.add(legacy)
        db.session.commit()

    response = client.get(f'/reset-password/{token}')
    assert response.status_code == 400


def test_email_domain_policy_rejects_subdomains_and_lookalikes():
    from app.routes import is_eligible_college_email

    assert is_eligible_college_email('student@aceec.ac.in')
    assert is_eligible_college_email('  STUDENT@ACEEC.AC.IN  ')
    assert not is_eligible_college_email('student@sub.aceec.ac.in')
    assert not is_eligible_college_email('student@aceec.ac.in.example.com')
    assert not is_eligible_college_email('student@gmail.com')
    assert not is_eligible_college_email('student@aceec.ac.in@evil.com')
    assert not is_eligible_college_email('student name@aceec.ac.in')
    assert not is_eligible_college_email('.student@aceec.ac.in')
    assert not is_eligible_college_email('student..name@aceec.ac.in')


def _session_csrf_token(client):
    """Return the CSRF token already established for this test-client session."""
    with client.session_transaction() as sess:
        token = sess.get('_csrf_token', '')
    assert token, 'test must establish a CSRF token before posting'
    return token


def _set_authenticated_user(client, user_id):
    """Authenticate a test client as an existing user for authorization boundary tests."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def test_non_owner_cannot_read_edit_analyze_simulate_delete_or_export_scenario(app, client):
    """A guessed scenario ID must not allow another student to read or mutate it."""
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=owner.id, title='Owner private scenario', domain='General',
                            change_variable='Time', current_value='10:00', proposed_value='11:00',
                            context='Synthetic authorization test')
        other = User(name='Other Student', email='other@aceec.ac.in', role='student')
        other.set_password('another-correct-password')
        db.session.add_all([scenario, other])
        db.session.commit()
        scenario_id, other_id = scenario.id, other.id

    _set_authenticated_user(client, other_id)
    urls_and_methods = [
        ('GET', f'/scenarios/{scenario_id}'),
        ('GET', f'/scenarios/{scenario_id}/edit'),
        ('POST', f'/scenarios/{scenario_id}/edit'),
        ('POST', f'/scenarios/{scenario_id}/analyze'),
        ('POST', f'/scenarios/{scenario_id}/simulate'),
        ('POST', f'/scenarios/{scenario_id}/delete'),
        ('GET', f'/scenarios/{scenario_id}/export.csv'),
        ('GET', f'/scenarios/{scenario_id}/export.json'),
    ]
    csrf = _session_csrf_token(client)
    for method, path in urls_and_methods:
        data = {'_csrf_token': csrf, 'alternative_value': '09:00'} if method == 'POST' else None
        response = client.open(path, method=method, data=data)
        assert response.status_code == 404, f'{method} {path} should conceal another user\'s scenario'

    with app.app_context():
        stored = db.session.get(Scenario, scenario_id)
        assert stored is not None, 'Denied delete attempt must not remove the scenario'
        assert stored.status == 'Draft', 'Denied actions must not change scenario status'
        assert stored.proposed_value == '11:00', 'Denied edit/simulation must not change scenario data'


def test_student_cannot_change_another_users_role(app, client):
    register(client)
    with app.app_context():
        target = User(name='Target Student', email='target@aceec.ac.in', role='student')
        target.set_password('another-correct-password')
        db.session.add(target)
        db.session.commit()
        target_id = target.id

    response = client.post(f'/admin/users/{target_id}/role', data={
        '_csrf_token': _session_csrf_token(client), 'role': 'admin'
    })
    assert response.status_code == 403
    with app.app_context():
        target = db.session.get(User, target_id)
        assert target.role == 'student'


def test_coordinator_can_approve_but_cannot_edit_non_owned_scenario(app, client):
    register(client)
    with app.app_context():
        owner = User.query.filter_by(email='student@aceec.ac.in').first()
        scenario = Scenario(user_id=owner.id, title='Approval boundary scenario', domain='General',
                            change_variable='Time', current_value='10:00', proposed_value='11:00',
                            context='Synthetic authorization test')
        coordinator = User(name='Coordinator', email='coordinator@aceec.ac.in', role='coordinator')
        coordinator.set_password('coordinator-correct-password')
        db.session.add_all([scenario, coordinator])
        db.session.commit()
        scenario_id, coordinator_id = scenario.id, coordinator.id

    _set_authenticated_user(client, coordinator_id)
    denied_edit = client.get(f'/scenarios/{scenario_id}/edit')
    assert denied_edit.status_code == 404
    approved = client.post(f'/scenarios/{scenario_id}/approval', data={
        '_csrf_token': _session_csrf_token(client),
        'action': 'approve', 'approval_note': 'Reviewed in authorization test'
    })
    assert approved.status_code == 302
    with app.app_context():
        stored = db.session.get(Scenario, scenario_id)
        assert stored.status == 'Approved'
        assert stored.approval_note == 'Reviewed in authorization test'


def test_admin_route_matrix_enforces_admin_only_access(app, client):
    """All non-admin roles are denied across all admin-only read routes."""
    register(client)
    with app.app_context():
        role_ids = {}
        for role in ('student', 'faculty', 'coordinator', 'admin'):
            user = User(name=f'{role.title()} Test', email=f'{role}-matrix@aceec.ac.in', role=role)
            user.set_password(f'{role}-test-password-2026')
            db.session.add(user)
        db.session.commit()
        for role in ('student', 'faculty', 'coordinator', 'admin'):
            role_ids[role] = User.query.filter_by(email=f'{role}-matrix@aceec.ac.in').first().id

    admin_routes = ('/admin/users', '/admin/integrations', '/admin/audit', '/admin/impact-quality')
    for role, user_id in role_ids.items():
        _set_authenticated_user(client, user_id)
        for path in admin_routes:
            response = client.get(path)
            expected = 200 if role == 'admin' else 403
            assert response.status_code == expected, (
                f'{role} expected HTTP {expected} for {path}, got {response.status_code}'
            )


def test_department_management_requires_coordinator_or_admin(app, client):
    """A role boundary is tested with a valid CSRF token so CSRF cannot mask authorization."""
    register(client)
    with app.app_context():
        role_ids = {}
        for role in ('student', 'faculty', 'coordinator', 'admin'):
            user = User(name=f'{role.title()} Manager Test', email=f'{role}-manage@aceec.ac.in', role=role)
            user.set_password(f'{role}-manage-password-2026')
            db.session.add(user)
        db.session.commit()
        for role in ('student', 'faculty', 'coordinator', 'admin'):
            role_ids[role] = User.query.filter_by(email=f'{role}-manage@aceec.ac.in').first().id

    csrf = _session_csrf_token(client)
    for role, user_id in role_ids.items():
        _set_authenticated_user(client, user_id)
        response = client.post('/college-workspace/departments', data={
            '_csrf_token': csrf, 'code': '', 'name': ''
        })
        if role in ('coordinator', 'admin'):
            assert response.status_code == 302, f'{role} should pass role gate and receive validation redirect'
        else:
            assert response.status_code == 403, f'{role} must not manage departments'
    with app.app_context():
        assert Department.query.count() == 0, 'invalid test payload must not create a department'
