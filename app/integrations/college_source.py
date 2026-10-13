"""Read-only adapter for an institution-approved timetable API.

Expected JSON response: {"timetable": [{"record_id", "department_code",
"department_name", "course_code", "course_name", "academic_year", "semester",
"room_code", "room_name", "room_type", "capacity", "faculty_name",
"day_of_week", "start_time", "end_time", "subject"}]}. Provider credentials and
an endpoint must be supplied by the institution; this adapter does not guess a vendor API.
"""
import json
import urllib.error
import urllib.request
import time
import re
from urllib.parse import urlparse

REQUIRED_FIELDS = (
    'department_code', 'department_name', 'course_code', 'course_name',
    'academic_year', 'semester', 'room_code', 'room_name', 'faculty_name',
    'day_of_week', 'start_time', 'end_time', 'subject'
)
VALID_DAYS = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}


class CollegeSourceError(RuntimeError):
    pass


def validate_timetable_payload(payload):
    """Validate and normalize the documented provider contract without network access.

    Duplicate provider record IDs are rejected so one malformed response cannot silently
    update the same local timetable row more than once. This function does not assert that
    provider data is authentic; endpoint/token authorization and institutional reconciliation
    remain separate requirements.
    """
    rows = payload.get('timetable') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) > 5000:
        raise CollegeSourceError('Expected a timetable array with at most 5000 rows.')
    validated = []
    seen_record_ids = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise CollegeSourceError(f'Row {index} must be a JSON object.')
        missing = [field for field in REQUIRED_FIELDS if row.get(field) is None or not str(row.get(field, '')).strip()]
        if missing:
            raise CollegeSourceError(f'Row {index} is missing required fields: {", ".join(missing)}.')
        clean = {field: str(row.get(field, '')).strip() for field in REQUIRED_FIELDS}
        max_lengths = {'department_code': 16, 'department_name': 120, 'course_code': 24,
                       'course_name': 120, 'academic_year': 20, 'semester': 20,
                       'room_code': 24, 'room_name': 120, 'faculty_name': 100, 'subject': 120}
        too_long = [field for field, maximum in max_lengths.items() if len(clean[field]) > maximum]
        if too_long:
            raise CollegeSourceError(f'Row {index} has fields longer than the supported limits: {", ".join(too_long)}.')
        record_id = str(row.get('record_id', '')).strip()
        if len(record_id) > 100:
            raise CollegeSourceError(f'Row {index} record_id exceeds the 100-character limit.')
        if record_id and record_id in seen_record_ids:
            raise CollegeSourceError(f'Row {index} duplicates provider record_id {record_id!r}.')
        if record_id:
            seen_record_ids.add(record_id)
        clean['record_id'] = record_id
        if clean['day_of_week'].title() not in VALID_DAYS:
            raise CollegeSourceError(f'Row {index} has an invalid day_of_week.')
        clean['day_of_week'] = clean['day_of_week'].title()
        minutes = {}
        for field in ('start_time', 'end_time'):
            value = clean[field]
            if len(value) != 5 or value[2] != ':' or not value[:2].isdigit() or not value[3:].isdigit():
                raise CollegeSourceError(f'Row {index} has invalid {field}; expected HH:MM.')
            hour, minute = int(value[:2]), int(value[3:])
            if hour > 23 or minute > 59:
                raise CollegeSourceError(f'Row {index} has invalid {field}; expected HH:MM.')
            minutes[field] = hour * 60 + minute
        if minutes['start_time'] >= minutes['end_time']:
            raise CollegeSourceError(f'Row {index} end_time must be after start_time.')
        capacity_value = row.get('capacity', 0)
        if isinstance(capacity_value, bool):
            raise CollegeSourceError(f'Row {index} capacity must be an integer.')
        if isinstance(capacity_value, str) and not re.fullmatch(r'[+-]?\d+', capacity_value.strip() or '0'):
            raise CollegeSourceError(f'Row {index} capacity must be a whole integer.')
        if isinstance(capacity_value, float) and not capacity_value.is_integer():
            raise CollegeSourceError(f'Row {index} capacity must be a whole integer.')
        try:
            capacity = int(capacity_value or 0)
        except (ValueError, TypeError, OverflowError) as exc:
            raise CollegeSourceError(f'Row {index} capacity must be an integer.') from exc
        if capacity < 0 or capacity > 10000:
            raise CollegeSourceError(f'Row {index} capacity must be between 0 and 10000.')
        clean['capacity'] = capacity
        clean['room_type'] = str(row.get('room_type') or 'Classroom').strip()[:24] or 'Classroom'
        validated.append(clean)
    return validated


def fetch_timetable(app):
    endpoint = str(app.config.get('COLLEGE_DATA_API_URL') or '').strip()
    token = str(app.config.get('COLLEGE_DATA_API_TOKEN') or '').strip()
    if not endpoint or not token:
        raise CollegeSourceError('Official data connector is not configured; set the approved endpoint and token.')
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise CollegeSourceError('Official data API must use HTTPS and must not embed credentials or fragments in its URL.')
    request = urllib.request.Request(endpoint, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': 'CampusRipple-CollegeDataAdapter/1.0'
    }, method='GET')
    raw = None
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=int(app.config.get('COLLEGE_DATA_API_TIMEOUT', 15))) as response:
                if response.status != 200:
                    raise CollegeSourceError(f'Official data API returned HTTP {response.status}.')
                raw = response.read(5 * 1024 * 1024 + 1)
            break
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == 2:
                raise CollegeSourceError(f'Official data API returned HTTP {exc.code}.') from exc
            last_error = exc
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 2:
                raise CollegeSourceError(f'Official data API request failed ({type(exc).__name__}).') from exc
        time.sleep(0.5 * (2 ** attempt))
    if raw is None:
        raise CollegeSourceError(f'Official data API request failed ({type(last_error).__name__ if last_error else "unknown error"}).')
    if len(raw) > 5 * 1024 * 1024:
        raise CollegeSourceError('Official data response exceeded the 5 MB limit.')
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollegeSourceError('Official data API did not return valid UTF-8 JSON.') from exc
    return validate_timetable_payload(payload)
