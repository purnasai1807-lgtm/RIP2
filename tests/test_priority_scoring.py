from app.priority_scoring import score_activities


def test_priority_score_outputs_high_medium_low_and_summary():
    rows = [
        {'activity_id': 'A1', 'priority': 'critical', 'priority_weight': 1200},
        {'activity_id': 'A2', 'priority': 'medium', 'priority_weight': 400},
        {'activity_id': 'A3', 'priority': 'low', 'priority_weight': 100},
    ]
    scored, summary = score_activities(rows)
    assert [row['level'] for row in scored] == ['High', 'Medium', 'Low']
    assert all(0 <= row['score'] <= 100 for row in scored)
    assert summary == {'total': 3, 'high': 1, 'medium': 1, 'low': 1, 'max_weight': 1200.0}


def test_zero_weights_do_not_divide_by_zero():
    scored, summary = score_activities([
        {'activity_id': 'A1', 'priority': 'low', 'priority_weight': 0},
    ])
    assert scored[0]['score'] == 15
    assert scored[0]['level'] == 'Low'
    assert summary['total'] == 1
