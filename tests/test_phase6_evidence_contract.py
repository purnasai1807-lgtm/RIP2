from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phase6_evidence_helpers', ROOT / 'app' / 'evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def test_phase6_routes_and_migration_are_registered():
    routes = (ROOT / 'app' / 'routes.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations' / 'versions' / '20261013_13_uncertainty_evidence.py').read_text(encoding='utf-8')
    template = (ROOT / 'app' / 'templates' / 'scenario_detail.html').read_text(encoding='utf-8')
    assert "'/scenarios/<int:scenario_id>/evidence'" in routes
    assert "'/scenarios/<int:scenario_id>/sensitivity'" in routes
    assert "'/scenarios/<int:scenario_id>/evidence/<int:evidence_id>/update'" in routes
    assert 'scenario_evidence' in migration
    assert 'PHASE 6' in template
    assert "down_revision = '20261013_12'" in migration


def test_phase6_docs_explain_uncertainty_and_non_mutating_sensitivity():
    docs = (ROOT / 'docs' / 'PHASE6_UNCERTAINTY_EVIDENCE.md').read_text(encoding='utf-8').lower()
    assert 'confidence' in docs and 'stale' in docs and 'does not change the saved evidence' in docs
