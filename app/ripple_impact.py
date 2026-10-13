"""Phase 4: bounded multi-hop ripple tracing for campus incidents.

Traverses only explicit ActivityDependency records. Every result is a potential
exposure, not proof of service failure. No activity/resource status is mutated.
"""
from collections import defaultdict, deque
from datetime import datetime, timezone

_RANK = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}
_IMPORTANCE = {'Optional': 1, 'Preferred': 2, 'Required': 3, 'Critical': 4}


def _severity(base, importance, criticality, depth):
    base_rank = _RANK.get(base, 2)
    imp = _IMPORTANCE.get(importance, 3)
    crit = _RANK.get(criticality, 2)
    # Depth never lowers severity; critical activities and critical dependencies raise it.
    rank = min(4, max(base_rank, round((base_rank + imp + crit) / 3)))
    return next(name for name, value in _RANK.items() if value == rank)


def analyze_ripple_impacts(incident, dependencies, constraints=(), max_depth=5):
    """Trace resource/activity effects through dependent activities, up to max_depth."""
    max_depth = max(1, min(int(max_depth or 5), 8))
    by_resource = defaultdict(list)
    by_target_activity = defaultdict(list)
    for dep in dependencies:
        if getattr(dep, 'target_resource_id', None) is not None:
            by_resource[dep.target_resource_id].append(dep)
        elif getattr(dep, 'target_activity_id', None) is not None:
            by_target_activity[dep.target_activity_id].append(dep)

    rows = {}
    queue = deque()
    source_refs = set()
    limitations = []

    def add_activity(activity, depth, parent, relation, dependency=None):
        key = f'activity:{activity.id}'
        if key in rows:
            # Keep the shortest path and best severity; record alternate causal links.
            row = rows[key]
            if depth < row['level']:
                row['level'] = depth
                row['parent'] = parent
                row['relationship'] = relation
            row['severity'] = max((row['severity'], _severity(incident.severity,
                getattr(dependency, 'importance', 'Required'), activity.criticality, depth)), key=lambda s: _RANK[s])
            if relation not in row['alternate_paths']:
                row['alternate_paths'].append(relation)
            return
        row = {
            'impact_key': key, 'level': depth, 'kind': 'activity', 'code': activity.code,
            'name': activity.name, 'location': activity.location or 'Not specified',
            'severity': _severity(incident.severity, getattr(dependency, 'importance', 'Required'), activity.criticality, depth),
            'parent': parent, 'relationship': relation,
            'source': f'campus_activity:{activity.id}',
            'evidence_status': 'explicit dependency record; operational effect unverified',
            'mitigation': ('Confirm prerequisites and notify the activity owner; evaluate a safe alternate plan. '
                'Do not cancel or reschedule until the responsible owner approves.'),
            'alternate_paths': [],
        }
        rows[key] = row
        source_refs.add(row['source'])
        queue.append((activity.id, depth, activity))

    seed_nodes = []
    if incident.resource is not None:
        resource = incident.resource
        key = f'resource:{resource.id}'
        rows[key] = {
            'impact_key': key, 'level': 0, 'kind': 'resource', 'code': resource.code,
            'name': resource.name, 'location': resource.location or incident.location or 'Not specified',
            'severity': incident.severity, 'parent': incident.incident_code,
            'relationship': 'Resource directly linked to the reported incident.',
            'source': f'campus_resource:{resource.id}', 'evidence_status': 'incident-linked record; condition unverified',
            'mitigation': 'Verify the condition with the resource owner and record the confirmed operational status.',
            'alternate_paths': [],
        }
        source_refs.add(rows[key]['source'])
        for dep in by_resource.get(resource.id, []):
            activity = getattr(dep, 'source_activity', None)
            if activity is not None:
                add_activity(activity, 1, resource.code,
                    f'{activity.code} depends on resource {resource.code} ({dep.dependency_type}; importance {dep.importance}).', dep)
        matched_constraints = [c for c in constraints if c.resource_id == resource.id]
        for c in matched_constraints:
            ckey = f'constraint:{c.id}'
            rows[ckey] = {
                'impact_key': ckey, 'level': 1, 'kind': 'constraint', 'code': f'CON-{c.id}',
                'name': f'{c.constraint_type} {c.operator} {c.limit_value} {c.unit}'.strip(),
                'location': resource.location or 'Not specified', 'severity': incident.severity,
                'parent': resource.code,
                'relationship': ('Hard' if c.is_hard_constraint else 'Soft') + ' constraint attached to the incident-linked resource; feasibility requires owner validation.',
                'source': f'resource_constraint:{c.id}', 'evidence_status': 'constraint record; violation not evaluated',
                'mitigation': 'Validate the constraint using current measurements and the accountable resource owner.',
                'alternate_paths': [],
            }
            source_refs.add(rows[ckey]['source'])
    if incident.activity is not None:
        activity = incident.activity
        add_activity(activity, 0, incident.incident_code,
                     'Activity directly linked to the reported incident.')

    # BFS: a source activity is affected when one of its prerequisite activities is affected.
    visited_depth = {}
    while queue:
        target_id, depth, target_activity = queue.popleft()
        if depth >= max_depth:
            continue
        if target_id in visited_depth and visited_depth[target_id] <= depth:
            continue
        visited_depth[target_id] = depth
        for dep in by_target_activity.get(target_id, []):
            dependent = getattr(dep, 'source_activity', None)
            if dependent is None:
                continue
            add_activity(dependent, depth + 1, target_activity.code,
                f'{dependent.code} depends on activity {target_activity.code} ({dep.dependency_type}; importance {dep.importance}).', dep)

    impacts = sorted(rows.values(), key=lambda r: (r['level'], -_RANK.get(r['severity'], 2), r['kind'], r['name'].casefold()))
    if incident.resource_id is None and incident.activity_id is None:
        limitations.append('No resource or activity is linked to this incident; graph tracing cannot establish a starting point.')
    if not dependencies:
        limitations.append('No dependency records are available. Add and verify Phase 1 dependency records for meaningful ripple tracing.')
    if any(r['level'] == max_depth for r in impacts):
        limitations.append(f'Traversal was bounded to {max_depth} dependency levels; deeper effects may exist.')
    limitations.append('All downstream records are potential exposures inferred from explicit links. The engine does not verify live service state, infer probabilities, change statuses, cancel activities, or approve mitigations.')
    if incident.status in ('Resolved', 'False alarm'):
        limitations.append(f'The incident is marked {incident.status}; this is a point-in-time graph trace, not a live active-impact count.')
    counts = {str(level): sum(1 for r in impacts if r['level'] == level) for level in sorted({r['level'] for r in impacts})}
    return {
        'incident': {'id': incident.id, 'code': incident.incident_code, 'title': incident.title,
                     'severity': incident.severity, 'status': incident.status},
        'analysis_type': 'bounded-multi-hop-ripple', 'analyzed_at': datetime.now(timezone.utc).isoformat(),
        'max_depth': max_depth, 'impact_count': len(impacts), 'level_counts': counts,
        'impacts': impacts, 'source_refs': sorted(source_refs), 'limitations': limitations,
        'method': 'Breadth-first traversal of explicit activity prerequisites, seeded by the incident-linked resource/activity; duplicate nodes are consolidated and the shortest discovered path is shown.'
    }
