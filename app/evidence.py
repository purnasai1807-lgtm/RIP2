"""Conservative, record-level evidence helpers for impact analysis.

Only exact conflicts supported by stored rows are labelled as database evidence.
Free-text scenarios that cannot be mapped to a specific resource/session are reported
as insufficient data instead of being promoted to a confirmed conflict.
"""
from datetime import datetime
import re

DAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')


def parse_interval(value, default_minutes=60):
    """Parse HH:MM or HH:MM-HH:MM into minute offsets; return None if ambiguous."""
    if not value:
        return None
    text = str(value).strip().replace('–', '-').replace('—', '-')
    matches = re.findall(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)', text)
    if not matches:
        return None
    start = int(matches[0][0]) * 60 + int(matches[0][1])
    if len(matches) >= 2:
        end = int(matches[1][0]) * 60 + int(matches[1][1])
    else:
        end = start + default_minutes
    if start >= end or end > 24 * 60:
        return None
    return start, end


def overlaps(a, b):
    return bool(a and b and a[0] < b[1] and b[0] < a[1])


def context_day(context):
    value = str(context or '').casefold()
    return next((day for day in DAYS if re.search(r'\b' + day.casefold() + r'\b', value)), None)


def context_matches_entry(context, entry):
    """Require at least one meaningful identifier from context to match a row."""
    text = str(context or '').casefold()
    identifiers = [entry.subject, entry.faculty_name, entry.room.code, entry.room.name,
                   entry.course.code, entry.course.name]
    return any(len(str(identifier or '').strip()) >= 3 and str(identifier).casefold() in text
               for identifier in identifiers)


def evidence_item(level, activity, description, cause, mitigation, source, evidence_ref,
                  severity='High', likelihood='High', parent_activity='Proposed change'):
    return {'level': level, 'activity': activity[:140], 'description': description,
            'cause': cause, 'severity': severity, 'likelihood': likelihood,
            'mitigation': mitigation, 'source': source, 'evidence_ref': evidence_ref,
            'parent_activity': parent_activity}


def compare_impacts(baseline, alternative):
    """Compare stable impact signatures; counts are transparent, not a risk score."""
    def signature(item):
        return (item.get('level'), item.get('activity'), item.get('evidence_ref'))
    before = {signature(item): item for item in baseline}
    after = {signature(item): item for item in alternative}
    return {
        'resolved': [before[key] for key in sorted(before.keys() - after.keys(), key=str)],
        'remaining': [after[key] for key in sorted(before.keys() & after.keys(), key=str)],
        'new': [after[key] for key in sorted(after.keys() - before.keys(), key=str)],
        'baseline_count': len(before), 'alternative_count': len(after),
    }
