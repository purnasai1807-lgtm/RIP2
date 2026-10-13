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


def test_uploaded_activities_csv_sample_scores_all_rows():
    import csv
    from pathlib import Path

    sample = Path(__file__).resolve().parents[1] / 'data' / 'samples' / 'activities_priority_example.csv'
    with sample.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    required = {'activity_id', 'activity_name', 'priority', 'priority_weight'}
    assert len(rows) == 35
    assert required <= set(rows[0])
    scored, summary = score_activities([
        {**row, 'priority_weight': float(row['priority_weight'])}
        for row in rows
    ])
    assert summary == {'total': 35, 'high': 8, 'medium': 23, 'low': 4, 'max_weight': 1400.0}
    assert all(0 <= row['score'] <= 100 for row in scored)
    assert all(row['level'] in {'High', 'Medium', 'Low'} for row in scored)
    assert scored[0]['activity_id'] == 'A01'
    assert scored[0]['score'] == 94
    assert scored[0]['level'] == 'High'
