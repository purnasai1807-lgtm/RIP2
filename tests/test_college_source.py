"""Provider-contract tests; all payloads are synthetic and are not college records."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

# Load this dependency-light adapter directly so contract validation tests can run even
# when Flask dependencies are not installed in a minimal offline development environment.
_SOURCE_PATH = Path(__file__).resolve().parents[1] / 'app' / 'integrations' / 'college_source.py'
_SPEC = importlib.util.spec_from_file_location('campusripple_college_source', _SOURCE_PATH)
_SOURCE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SOURCE)
CollegeSourceError = _SOURCE.CollegeSourceError
fetch_timetable = _SOURCE.fetch_timetable
validate_timetable_payload = _SOURCE.validate_timetable_payload


def valid_row(**overrides):
    row = {
        'record_id': 'synthetic-1',
        'department_code': 'DEMO-CSD',
        'department_name': 'DEMO Department',
        'course_code': 'DEMO-101',
        'course_name': 'DEMO Course',
        'academic_year': '2026-27',
        'semester': '1',
        'room_code': 'DEMO-R1',
        'room_name': 'DEMO Room',
        'room_type': 'Classroom',
        'capacity': 40,
        'faculty_name': 'DEMO Faculty',
        'day_of_week': 'Monday',
        'start_time': '09:00',
        'end_time': '10:00',
        'subject': 'DEMO Subject',
    }
    row.update(overrides)
    return row


def test_provider_payload_is_normalized():
    rows = validate_timetable_payload({'timetable': [valid_row(day_of_week='monday')]})
    assert len(rows) == 1
    assert rows[0]['day_of_week'] == 'Monday'
    assert rows[0]['capacity'] == 40
    assert rows[0]['record_id'] == 'synthetic-1'


@pytest.mark.parametrize('payload', [None, [], {}, {'timetable': 'not-a-list'}, {'timetable': [None]}])
def test_provider_payload_rejects_invalid_shapes(payload):
    with pytest.raises(CollegeSourceError):
        validate_timetable_payload(payload)


@pytest.mark.parametrize('overrides', [
    {'start_time': '9am'},
    {'start_time': '12:90'},
    {'start_time': '10:00', 'end_time': '10:00'},
    {'day_of_week': 'Funday'},
    {'capacity': True},
    {'capacity': 2.5},
    {'capacity': -1},
    {'record_id': 'x' * 101},
])
def test_provider_row_rejects_invalid_fields(overrides):
    with pytest.raises(CollegeSourceError):
        validate_timetable_payload({'timetable': [valid_row(**overrides)]})


def test_duplicate_provider_record_ids_are_rejected():
    with pytest.raises(CollegeSourceError, match='duplicates provider record_id'):
        validate_timetable_payload({'timetable': [valid_row(), valid_row()]})


def test_missing_connector_configuration_fails_closed():
    app = SimpleNamespace(config={'COLLEGE_DATA_API_URL': '', 'COLLEGE_DATA_API_TOKEN': ''})
    with pytest.raises(CollegeSourceError, match='not configured'):
        fetch_timetable(app)


def test_http_and_url_with_embedded_credentials_are_rejected_before_network():
    for endpoint in ('http://college.example/api', 'https://user:password@college.example/api'):
        app = SimpleNamespace(config={'COLLEGE_DATA_API_URL': endpoint, 'COLLEGE_DATA_API_TOKEN': 'test-token'})
        with pytest.raises(CollegeSourceError, match='HTTPS'):
            fetch_timetable(app)


def test_fetch_timetable_sends_bearer_token_and_validates_response(monkeypatch):
    body = json.dumps({'timetable': [valid_row()]}).encode('utf-8')

    class FakeResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return body

    seen = {}
    def fake_urlopen(request, timeout):
        seen['authorization'] = request.get_header('Authorization')
        seen['timeout'] = timeout
        return FakeResponse()

    monkeypatch.setattr(_SOURCE.urllib.request, 'urlopen', fake_urlopen)
    app = SimpleNamespace(config={
        'COLLEGE_DATA_API_URL': 'https://approved.example/api/timetable',
        'COLLEGE_DATA_API_TOKEN': 'synthetic-test-token',
        'COLLEGE_DATA_API_TIMEOUT': 7,
    })
    rows = fetch_timetable(app)
    assert len(rows) == 1
    assert seen == {'authorization': 'Bearer synthetic-test-token', 'timeout': 7}


def test_fetch_timetable_rejects_oversized_response(monkeypatch):
    class FakeResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, limit):
            return b'x' * limit

    monkeypatch.setattr(_SOURCE.urllib.request, 'urlopen', lambda *_args, **_kwargs: FakeResponse())
    app = SimpleNamespace(config={
        'COLLEGE_DATA_API_URL': 'https://approved.example/api/timetable',
        'COLLEGE_DATA_API_TOKEN': 'synthetic-test-token',
        'COLLEGE_DATA_API_TIMEOUT': 1,
    })
    with pytest.raises(CollegeSourceError, match='5 MB limit'):
        fetch_timetable(app)


def test_fetch_timetable_rejects_invalid_json_without_leaking_payload(monkeypatch):
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _limit): return b'{not-json'
    monkeypatch.setattr(_SOURCE.urllib.request, 'urlopen', lambda *_args, **_kwargs: FakeResponse())
    app = SimpleNamespace(config={'COLLEGE_DATA_API_URL': 'https://approved.example/api', 'COLLEGE_DATA_API_TOKEN': 'synthetic-test-token', 'COLLEGE_DATA_API_TIMEOUT': 1})
    with pytest.raises(CollegeSourceError, match='valid UTF-8 JSON'):
        fetch_timetable(app)


def test_fetch_timetable_does_not_retry_client_authentication_errors(monkeypatch):
    calls = {'count': 0}
    def fail(*_args, **_kwargs):
        calls['count'] += 1
        raise _SOURCE.urllib.error.HTTPError('https://approved.example/api', 401, 'unauthorized', {}, None)
    monkeypatch.setattr(_SOURCE.urllib.request, 'urlopen', fail)
    app = SimpleNamespace(config={'COLLEGE_DATA_API_URL': 'https://approved.example/api', 'COLLEGE_DATA_API_TOKEN': 'synthetic-test-token', 'COLLEGE_DATA_API_TIMEOUT': 1})
    with pytest.raises(CollegeSourceError, match='HTTP 401'):
        fetch_timetable(app)
    assert calls['count'] == 1


def test_fetch_timetable_retries_transient_server_error(monkeypatch):
    calls = {'count': 0}
    body = json.dumps({'timetable': [valid_row()]}).encode('utf-8')
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _limit): return body
    def transient_then_success(*_args, **_kwargs):
        calls['count'] += 1
        if calls['count'] == 1:
            raise _SOURCE.urllib.error.HTTPError('https://approved.example/api', 503, 'unavailable', {}, None)
        return FakeResponse()
    monkeypatch.setattr(_SOURCE.urllib.request, 'urlopen', transient_then_success)
    monkeypatch.setattr(_SOURCE.time, 'sleep', lambda *_args: None)
    app = SimpleNamespace(config={'COLLEGE_DATA_API_URL': 'https://approved.example/api', 'COLLEGE_DATA_API_TOKEN': 'synthetic-test-token', 'COLLEGE_DATA_API_TIMEOUT': 1})
    assert len(fetch_timetable(app)) == 1
    assert calls['count'] == 2
