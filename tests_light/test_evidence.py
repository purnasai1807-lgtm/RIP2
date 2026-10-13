"""Dependency-light tests for evidence parsing and impact-chain quality."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

evidence = load_module('campusripple_evidence', ROOT / 'app' / 'evidence.py')
engine = load_module('campusripple_engine', ROOT / 'app' / 'engine.py')


def test_interval_parser_handles_valid_intervals_and_rejects_ambiguous_values():
    assert evidence.parse_interval('09:30-10:45') == (570, 645)
    assert evidence.parse_interval('09:30') == (570, 630)
    assert evidence.parse_interval('23:30') is None
    assert evidence.parse_interval('10:30-09:30') is None
    assert evidence.parse_interval('after lunch') is None


def test_overlap_uses_half_open_intervals():
    assert evidence.overlaps((540, 600), (599, 660))
    assert not evidence.overlaps((540, 600), (600, 660))
    assert not evidence.overlaps(None, (540, 600))


def test_context_day_matches_whole_day_name_only():
    assert evidence.context_day('Move the session to Tuesday afternoon') == 'Tuesday'
    assert evidence.context_day('The student is on MondayRoad') is None


def test_compare_impacts_separates_resolved_remaining_and_new():
    baseline = [
        {'level': 1, 'activity': 'Room conflict', 'evidence_ref': 'room:1'},
        {'level': 2, 'activity': 'Lab delay', 'evidence_ref': None},
    ]
    alternative = [
        {'level': 1, 'activity': 'Room conflict', 'evidence_ref': 'room:1'},
        {'level': 1, 'activity': 'Transport issue', 'evidence_ref': 'route:2'},
    ]
    result = evidence.compare_impacts(baseline, alternative)
    assert [item['activity'] for item in result['resolved']] == ['Lab delay']
    assert [item['activity'] for item in result['remaining']] == ['Room conflict']
    assert [item['activity'] for item in result['new']] == ['Transport issue']
    assert result['baseline_count'] == 2
    assert result['alternative_count'] == 2


def test_evidence_parent_must_reference_an_actual_prior_level_activity():
    items = engine.analyze('General', 'Time', '10:00', '11:00', evidence=[{
        'level': 2,
        'activity': 'Record-backed downstream issue',
        'description': 'Synthetic test only',
        'cause': 'Test cause',
        'mitigation': 'Test mitigation',
        'source': 'synthetic test evidence',
        'evidence_ref': 'synthetic:123',
        'parent_activity': 'Made-up parent that does not exist',
    }])
    level_one_names = {item['activity'] for item in items if item['level'] == 1}
    downstream = next(item for item in items if item['activity'] == 'Record-backed downstream issue')
    assert downstream['parent_activity'] in level_one_names
    assert downstream['parent_activity'] != 'Made-up parent that does not exist'


def test_malformed_evidence_level_is_safely_downgraded_to_direct_level():
    items = engine.analyze('General', 'Time', '10:00', '11:00', evidence=[{
        'level': 'not-a-level', 'activity': 'Malformed level',
        'description': 'Synthetic test only', 'cause': 'Test cause', 'mitigation': 'Test mitigation',
    }])
    impact = next(item for item in items if item['activity'] == 'Malformed level')
    assert impact['level'] == 1
    assert impact['parent_activity'] == 'Proposed change'


def test_evidence_input_has_safe_required_text_defaults_and_severity_bounds():
    items = engine.analyze('General', 'Time', '10:00', '11:00', evidence=[{
        'level': 1, 'activity': 'Bounded activity', 'severity': 'Impossible', 'likelihood': 'Unknown',
    }])
    impact = next(item for item in items if item['activity'] == 'Bounded activity')
    assert impact['severity'] == 'Medium'
    assert impact['likelihood'] == 'Medium'
    assert impact['cause']
    assert impact['mitigation']


def test_phase5_reproducibility_contract_is_documented_and_migrated():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    docs = (root / 'docs' / 'PHASE5_DECISION_INTELLIGENCE.md').read_text(encoding='utf-8')
    migration = (root / 'migrations' / 'versions' / '20261013_12_analysis_reproducibility.py').read_text(encoding='utf-8')
    routes = (root / 'app' / 'routes.py').read_text(encoding='utf-8')
    assert 'deterministic replay' in docs.lower()
    assert "analysis_input_hash" in migration and "analysis_result_hash" in migration
    assert "'/scenarios/<int:scenario_id>/verify-analysis'" in routes
    assert "'/admin/impact-quality/export.csv'" in routes
