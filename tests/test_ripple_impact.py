from types import SimpleNamespace
from app.ripple_impact import analyze_ripple_impacts


def activity(i, code, name, criticality='Medium'):
    return SimpleNamespace(id=i, code=code, name=name, location='Block A', criticality=criticality)


def dependency(i, source, target_activity=None, target_resource=None, importance='Required'):
    return SimpleNamespace(id=i, source_activity=source, target_activity_id=target_activity.id if target_activity else None,
        target_resource_id=target_resource.id if target_resource else None, dependency_type='requires', importance=importance)


def test_ripple_analysis_traces_multi_hop_chain_and_explains_parent_path():
    resource = SimpleNamespace(id=1, code='PWR-A', name='Power service', location='Block A')
    a = activity(10, 'LAB-A', 'Programming lab', 'High')
    b = activity(11, 'EXAM-A', 'Practical exam', 'Critical')
    c = activity(12, 'REVIEW-A', 'Review session')
    incident = SimpleNamespace(id=3, incident_code='INC-1', title='Power issue', severity='High', status='Investigating',
        location='Block A', resource_id=1, activity_id=None, resource=resource, activity=None)
    deps = [dependency(1, a, target_resource=resource), dependency(2, b, target_activity=a), dependency(3, c, target_activity=b)]
    report = analyze_ripple_impacts(incident, deps, max_depth=5)
    levels = {row['code']: row['level'] for row in report['impacts']}
    assert levels == {'PWR-A': 0, 'LAB-A': 1, 'EXAM-A': 2, 'REVIEW-A': 3}
    assert report['analysis_type'] == 'bounded-multi-hop-ripple'
    assert next(row for row in report['impacts'] if row['code'] == 'EXAM-A')['parent'] == 'LAB-A'
    assert any('does not verify live service state' in x for x in report['limitations'])


def test_ripple_analysis_handles_unlinked_incident_and_bounds_depth():
    incident = SimpleNamespace(id=2, incident_code='INC-2', title='Unlinked', severity='Low', status='Reported',
        location='', resource_id=None, activity_id=None, resource=None, activity=None)
    report = analyze_ripple_impacts(incident, [], max_depth=999)
    assert report['impact_count'] == 0
    assert report['max_depth'] == 8
    assert any('No resource or activity is linked' in x for x in report['limitations'])
