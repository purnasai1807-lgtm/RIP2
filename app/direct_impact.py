"""Phase 3: deterministic, explainable direct-impact analysis for campus incidents.

This module intentionally analyzes only one dependency edge from an incident's linked
campus record. It does not claim indirect/ripple impacts; those belong to a later phase.
"""
from datetime import datetime, timezone

SEVERITY_RANK = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}
CRITICALITY_RANK = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}
IMPORTANCE_RANK = {'Optional': 1, 'Preferred': 2, 'Required': 3, 'Critical': 4}


def _raised_severity(incident_severity, importance='Required', criticality='Medium'):
    base = SEVERITY_RANK.get(incident_severity, 2)
    imp = IMPORTANCE_RANK.get(importance, 3)
    crit = CRITICALITY_RANK.get(criticality, 2)
    # Keep impact severity bounded by the reported incident severity. This is a
    # transparent prioritization heuristic, not a measured probability.
    rank = min(4, max(base, min(4, round((base + imp + crit) / 3))))
    return next(key for key, value in SEVERITY_RANK.items() if value == rank)


def analyze_direct_impacts(incident, dependencies, constraints):
    """Return direct impact records, limitations and source lineage for an incident."""
    impacts = []
    seen = set()
    source_refs = []

    def add(key, kind, code, name, location, reason, severity, source, mitigation, evidence_status='model-linked'):
        if key in seen:
            return
        seen.add(key)
        impacts.append({
            'impact_key': key, 'level': 1, 'kind': kind, 'code': code, 'name': name,
            'location': location or 'Not specified', 'severity': severity,
            'relationship': reason, 'source': source, 'evidence_status': evidence_status,
            'mitigation': mitigation,
        })
        source_refs.append(source)

    if incident.resource:
        resource = incident.resource
        add(f'resource:{resource.id}', 'resource', resource.code, resource.name, resource.location,
            'Resource directly linked to the reported incident.', incident.severity,
            f'campus_resource:{resource.id}',
            'Confirm resource condition with its owner; mark it unavailable only after verification.')
        for constraint in constraints:
            if constraint.resource_id != resource.id:
                continue
            add(f'constraint:{constraint.id}', 'constraint', f'CON-{constraint.id}',
                f'{constraint.constraint_type} {constraint.operator} {constraint.limit_value} {constraint.unit}'.strip(),
                resource.location,
                ('Hard' if constraint.is_hard_constraint else 'Soft') + ' constraint attached to the affected resource; assess whether the incident makes it infeasible.',
                incident.severity, f'resource_constraint:{constraint.id}',
                'Ask the resource owner to validate this constraint against current operating conditions.',
                'constraint-linked; feasibility not automatically evaluated')
        for dependency in dependencies:
            if dependency.target_resource_id != resource.id or not dependency.source_activity:
                continue
            activity = dependency.source_activity
            severity = _raised_severity(incident.severity, dependency.importance, activity.criticality)
            add(f'activity:{activity.id}', 'activity', activity.code, activity.name, activity.location,
                f'Activity depends on affected resource {resource.code} ({dependency.dependency_type}; importance: {dependency.importance}).',
                severity, f'activity_dependency:{dependency.id}',
                'Contact the activity owner; verify a backup resource or rescheduling option before changing the activity status.')

    if incident.activity:
        activity = incident.activity
        add(f'activity:{activity.id}', 'activity', activity.code, activity.name, activity.location,
            'Activity directly linked to the reported incident.', incident.severity,
            f'campus_activity:{activity.id}',
            'Confirm impact with the activity owner and affected participants before rescheduling or cancelling.')
        # In the data model, source_activity requires target_activity. Therefore, a
        # source activity is directly exposed when its required target is affected.
        for dependency in dependencies:
            if dependency.target_activity_id != activity.id or not dependency.source_activity:
                continue
            dependent = dependency.source_activity
            severity = _raised_severity(incident.severity, dependency.importance, dependent.criticality)
            add(f'activity:{dependent.id}', 'activity', dependent.code, dependent.name, dependent.location,
                f'Activity depends on directly affected activity {activity.code} ({dependency.dependency_type}; importance: {dependency.importance}).',
                severity, f'activity_dependency:{dependency.id}',
                'Contact the dependent activity owner and confirm whether the prerequisite is required before proceeding.')

    impacts.sort(key=lambda row: ( -SEVERITY_RANK.get(row['severity'], 2), row['kind'], row['name'].casefold()))
    limitations = []
    if not incident.resource_id and not incident.activity_id:
        limitations.append('No campus resource or activity is linked to this incident. Results cannot identify dependent records until a link is added.')
    if not dependencies:
        limitations.append('No dependency records were available to expand direct impacts. Check the Phase 1 campus data model.')
    limitations.append('Direct relationships are derived from the current campus model. They show exposure, not proof that an activity has stopped or that a constraint has been violated.')
    if incident.status in ('Resolved', 'False alarm'):
        limitations.append(f'The incident is marked “{incident.status}”; this analysis is a snapshot and should not be treated as a live active-impact count.')

    return {
        'incident': {
            'id': incident.id, 'code': incident.incident_code, 'title': incident.title,
            'severity': incident.severity, 'status': incident.status,
            'location': incident.location or None,
            'estimated_duration_minutes': incident.estimated_duration_minutes,
        },
        'analysis_type': 'direct-only',
        'analyzed_at': datetime.now(timezone.utc).isoformat(),
        'impact_count': len(impacts),
        'impacts': impacts,
        'source_refs': sorted(set(source_refs)),
        'limitations': limitations,
        'method': 'One-hop graph traversal from the incident-linked resource/activity. No indirect propagation, probabilities, or automatic status changes are performed.',
    }
