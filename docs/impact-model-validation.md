# Decision Impact Analysis validation protocol

The rule engine produces hypotheses. It is not a validated predictor until ACEEC stakeholders review representative cases and outcomes.

## Collecting a review set

1. Obtain approval from the academic/operations owner to use each case.
2. Remove personal data and use synthetic case IDs.
3. Have at least two domain reviewers independently list expected impact keys; resolve disagreements before labeling a case `stakeholder-reviewed`.
4. Record predicted keys from the exact rule version under evaluation; do not hand-edit predictions to match expected labels.
5. Include ordinary cases, high-impact changes, low/no-impact changes, incomplete evidence, and operational edge cases. Record source provenance and rule version.
6. Version the dataset and reviewer decisions. Separate development examples from a held-out acceptance set.

## Metrics

Run `python scripts/evaluate_impact_cases.py reviewed_cases.json`. The JSON must contain `review_status: "stakeholder-reviewed"` and cases with `case_id`, `expected_impact_keys`, and `predicted_impact_keys`.

The report calculates true positives, false positives, false negatives, precision, recall, and F1. Specificity/true negatives are deliberately not reported because impact-key matching does not define a closed universe of all possible impacts. Investigate each false positive/negative and report metrics by domain and severity as well as overall.

No reviewed dataset is bundled because ACEEC stakeholder-labeled ground truth was not supplied. Do not fabricate cases or describe synthetic demonstrations as validation.

## Input shape

```json
{
  "review_status": "stakeholder-reviewed",
  "cases": [
    {
      "case_id": "approved-case-id",
      "expected_impact_keys": ["reviewer-defined-key"],
      "predicted_impact_keys": ["engine-output-key"]
    }
  ]
}
```
