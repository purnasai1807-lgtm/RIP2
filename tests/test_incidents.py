from app import db
from app.models import User, CampusIncident, IncidentUpdate, CampusResource, CampusActivity


def login_as(client, app, role='coordinator'):
    with app.app_context():
        user = User.query.filter_by(email=f'{role}@aceec.ac.in').first()
        if user is None:
            user = User(email=f'{role}@aceec.ac.in', name=role.title(), role=role)
            user.set_password('correct-horse-battery')
            user.email_verified_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
            db.session.add(user)
            db.session.commit()
        user_id = user.id
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
        session['_csrf_token'] = 'test-csrf-token'
    return user_id


def test_incident_html_create_and_status_history(app, client):
    user_id = login_as(client, app)
    response = client.post('/incidents', data={
        '_csrf_token': 'test-csrf-token', 'incident_code': 'INC-POWER-01',
        'title': 'Building A power outage', 'description': 'Facilities team confirmed loss of power.',
        'incident_type': 'Power', 'severity': 'High', 'status': 'Reported',
        'location': 'Building A', 'estimated_duration_minutes': '120',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'INC-POWER-01' in response.data
    with app.app_context():
        item = CampusIncident.query.filter_by(incident_code='INC-POWER-01').one()
        assert item.reported_by_id == user_id
        assert item.estimated_duration_minutes == 120
        assert len(item.updates) == 1
        incident_id = item.id
    response = client.post(f'/incidents/{incident_id}/update', data={
        '_csrf_token': 'test-csrf-token', 'title': 'Building A power outage',
        'description': 'Utility crew is on site.', 'incident_type': 'Power', 'severity': 'Critical',
        'status': 'Investigating', 'location': 'Building A', 'estimated_duration_minutes': '90',
        'note': 'Utility crew confirmed an updated estimate.'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Investigating' in response.data
    with app.app_context():
        item = db.session.get(CampusIncident, incident_id)
        assert item.status == 'Investigating'
        assert item.severity == 'Critical'
        assert len(item.updates) == 2
        assert any(u.previous_status == 'Reported' and u.new_status == 'Investigating' for u in item.updates)


def test_incident_api_requires_authentication(client):
    assert client.get('/api/incidents').status_code == 401 or client.get('/api/incidents').status_code == 302


def test_incident_api_validates_fields_and_returns_history(app, client):
    login_as(client, app)
    response = client.post('/api/incidents', headers={'X-CSRF-Token':'test-csrf-token'}, json={
        'incident_code':'INC-NET-01', 'title':'Network outage', 'description':'Wi-Fi unavailable in library',
        'incident_type':'Network', 'severity':'High', 'location':'Library', 'estimated_duration_minutes':30
    })
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    assert data['incident_code'] == 'INC-NET-01'
    assert len(data['updates']) == 1
    bad = client.post('/api/incidents', headers={'X-CSRF-Token':'test-csrf-token'}, json={
        'title':'', 'description':'missing title', 'incident_type':'Unknown', 'severity':'Extreme'
    })
    assert bad.status_code == 400
    updated = client.patch(f"/api/incidents/{data['id']}", headers={'X-CSRF-Token':'test-csrf-token'}, json={
        'status':'Resolved', 'note':'Connectivity restored.'
    })
    assert updated.status_code == 200
    result = updated.get_json()
    assert result['status'] == 'Resolved'
    assert result['resolved_at']
    assert len(result['updates']) == 2


def test_students_can_read_but_cannot_create_incidents(app, client):
    login_as(client, app, 'student')
    assert client.get('/incidents').status_code == 200
    response = client.post('/api/incidents', headers={'X-CSRF-Token':'test-csrf-token'}, json={
        'title':'Unauthorized report', 'description':'Should be blocked'
    })
    assert response.status_code == 403


def test_incident_rejects_unknown_link_and_invalid_duration(app, client):
    login_as(client, app)
    response = client.post('/api/incidents', headers={'X-CSRF-Token':'test-csrf-token'}, json={
        'title':'Bad link', 'description':'Test', 'resource_id':999999, 'estimated_duration_minutes':0
    })
    assert response.status_code == 400
