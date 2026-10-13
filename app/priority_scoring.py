"""Deterministic priority scoring for uploaded campus activity CSV rows."""

PRIORITY_BASE = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}


def score_activities(rows):
    """Return scored row copies and summary; expects validated priority and weight fields.

    Score = 60% declared priority tier + 40% priority_weight normalized to the
    largest weight in the same upload. The score is a transparent relative
    decision-support indicator, not a probability or safety assessment.
    """
    rows = list(rows)
    max_weight = max((float(row['priority_weight']) for row in rows), default=0.0)
    scored = []
    for row in rows:
        priority = str(row['priority']).strip().lower()
        weight = float(row['priority_weight'])
        normalized_weight = round((weight / max_weight) * 100) if max_weight else 0
        score = round(PRIORITY_BASE[priority] * 0.6 + normalized_weight * 0.4)
        level = 'High' if score >= 70 else ('Medium' if score >= 40 else 'Low')
        scored.append({**row, 'priority': priority.title(), 'priority_weight': weight,
                       'score': score, 'level': level})
    summary = {
        'total': len(scored),
        'high': sum(row['level'] == 'High' for row in scored),
        'medium': sum(row['level'] == 'Medium' for row in scored),
        'low': sum(row['level'] == 'Low' for row in scored),
        'max_weight': max_weight,
    }
    return scored, summary
