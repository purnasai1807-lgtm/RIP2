import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_impact_cases.py"
spec = importlib.util.spec_from_file_location("impact_evaluation", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_metrics_match_stakeholder_reviewed_labels():
    result = module.evaluate({"review_status": "stakeholder-reviewed", "cases": [
        {"case_id": "A", "expected_impact_keys": ["room", "faculty"], "predicted_impact_keys": ["room", "transport"]},
        {"case_id": "B", "expected_impact_keys": ["exam"], "predicted_impact_keys": ["exam"]},
    ]})
    assert (result["true_positive"], result["false_positive"], result["false_negative"]) == (2, 1, 1)
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["f1"] == pytest.approx(2 / 3)
    assert result["specificity"] is None


@pytest.mark.parametrize("payload", [{}, {"review_status": "not-reviewed", "cases": [{"case_id": "A", "expected_impact_keys": [], "predicted_impact_keys": []}]}, {"review_status": "stakeholder-reviewed", "cases": []}])
def test_evaluator_rejects_missing_ground_truth(payload):
    with pytest.raises(ValueError):
        module.evaluate(payload)


def test_evaluator_rejects_duplicate_case_ids_and_keys():
    with pytest.raises(ValueError):
        module.evaluate({"review_status": "stakeholder-reviewed", "cases": [{"case_id": "A", "expected_impact_keys": ["x", "x"], "predicted_impact_keys": []}]})
