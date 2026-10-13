def test_phase9_outcome_review_route_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert '/scenarios/<int:scenario_id>/outcome-review' in rules

def test_phase9_migration_exists():
    from pathlib import Path
    assert Path('migrations/versions/20261013_15_phase9_outcome_review.py').is_file()
