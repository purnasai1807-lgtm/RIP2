"""Calculate impact-detection metrics from stakeholder-reviewed JSON cases.

Input format: {"review_status":"stakeholder-reviewed", "cases":[
 {"case_id":"CASE-001", "expected_impact_keys":["room_conflict"],
  "predicted_impact_keys":["room_conflict", "transport_delay"]}]}

Keys must be stable identifiers agreed by reviewers. No ground truth is fabricated.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def evaluate(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("review_status") != "stakeholder-reviewed":
        raise ValueError("Input must be explicitly marked review_status='stakeholder-reviewed'.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("At least one stakeholder-reviewed case is required.")
    seen_cases, total_keys = set(), set()
    tp = fp = fn = 0
    details = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be an object.")
        case_id = str(case.get("case_id", "")).strip()
        if not case_id or case_id in seen_cases:
            raise ValueError(f"Case {index} needs a unique non-empty case_id.")
        seen_cases.add(case_id)
        expected, predicted = case.get("expected_impact_keys"), case.get("predicted_impact_keys")
        if not isinstance(expected, list) or not isinstance(predicted, list):
            raise ValueError(f"{case_id}: expected and predicted impact keys must be lists.")
        if any(not isinstance(k, str) or not k.strip() for k in expected + predicted):
            raise ValueError(f"{case_id}: impact keys must be non-empty strings.")
        if len(set(expected)) != len(expected) or len(set(predicted)) != len(predicted):
            raise ValueError(f"{case_id}: duplicate impact keys are not allowed.")
        e, p = set(expected), set(predicted)
        hits, extras, missed = e & p, p - e, e - p
        tp += len(hits); fp += len(extras); fn += len(missed)
        total_keys.update(e | p)
        details.append({"case_id": case_id, "true_positive": sorted(hits),
                        "false_positive": sorted(extras), "false_negative": sorted(missed)})
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {"cases_reviewed": len(cases), "unique_impact_keys_observed": len(total_keys),
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": precision, "recall": recall, "f1": f1, "specificity": None,
            "note": "Metrics apply only to supplied stakeholder-reviewed labels and key matching. Specificity is not reported because no closed universe of possible impacts was supplied.",
            "case_details": details}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("Usage: python scripts/evaluate_impact_cases.py reviewed_cases.json", file=sys.stderr)
        return 2
    try:
        result = evaluate(json.loads(Path(args[0]).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
