from types import SimpleNamespace
from app.direct_impact import analyze_direct_impacts


def test_resource_incident_finds_directly_dependent_activity_and_constraints():
    resource = SimpleNamespace(id=7, code='PWR-A', name='Building A power', location='Building A')
    activity = SimpleNamespace(id=11, code='WS-01', name='Python workshop', location='Building A', criticality='High')
    incident = SimpleNamespace(id=3, incident_code='INC-PWR-01', title='Power outage', severity='High', status='Investigating',
        location='Building A', estimated_duration_minutes=120, resource_id=7, activity_id=None, resource=resource, activity=None)
    dependency = SimpleNamespace(id=4, target_resource_id=7, target_activity_id=None, source_activity=activity,
        dependency_type='requires', importance='Required')
    constraint = SimpleNamespace(id=5, resource_id=7, constraint_type='Capacity', operator='<=', limit_value='60', unit='people',
        is_hard_constraint=True)

    report = analyze_direct_impacts(incident, [dependency], [constraint])

    assert report['analysis_type'] == 'direct-only'
    assert report['impact_count'] == 3
    assert {row['impact_key'] for row in report['impacts']} == {'resource:7', 'activity:11', 'constraint:5'}
    assert any('depends on affected resource' in row['relationship'] for row in report['impacts'])
    assert any(row['source'] == 'resource_constraint:5' for row in report['impacts'])
    assert 'not proof' in report['limitations'][-1].lower()


def test_activity_incident_finds_only_immediate_dependents_and_no_false_resource_claim():
    affected = SimpleNamespace(id=11, code='EXAM-1', name='Midterm exam', location='Block C', criticality='Critical')
    dependent = SimpleNamespace(id=12, code='REV-1', name='Review session', location='Block C', criticality='Medium')
    incident = SimpleNamespace(id=8, incident_code='INC-EXAM-1', title='Exam room issue', severity='Medium', status='Reported',
        location='Block C', estimated_duration_minutes=None, resource_id=None, activity_id=11, resource=None, activity=affected)
    dependency = SimpleNamespace(id=21, target_resource_id=None, target_activity_id=11, source_activity=dependent,
        dependency_type='requires', importance='Required')

    report = analyze_direct_impacts(incident, [dependency], [])

    assert report['impact_count'] == 2
    assert {row['impact_key'] for row in report['impacts']} == {'activity:11', 'activity:12'}
    assert all(row['kind'] == 'activity' for row in report['impacts'])
    assert any('depends on directly affected activity' in row['relationship'] for row in report['impacts'])


def test_unlinked_incident_returns_explicit_data_gap():
    incident = SimpleNamespace(id=1, incident_code='INC-OTHER-1', title='Unlinked issue', severity='Low', status='Reported',
        location='', estimated_duration_minutes=None, resource_id=None, activity_id=None, resource=None, activity=None)
    report = analyze_direct_impacts(incident, [], [])
    assert report['impact_count'] == 0
    assert any('No campus resource or activity is linked' in note for note in report['limitations'])
    assert report['analysis_type'] == 'direct-only'
