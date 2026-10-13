"""Analyze a scenario supplied from authorized, real institutional data.

No example scenario or college data is embedded in this script. The engine is
rule-based; its outputs remain hypotheses unless tied to verified records.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "app" / "engine.py"
spec = importlib.util.spec_from_file_location("campusripple_engine", ENGINE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load the decision impact engine")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

REQUIRED = ("domain", "change_variable", "current_value", "proposed_value", "context", "source_reference")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", help="Path to a JSON file containing an authorized real decision; no sample data is bundled")
    args = parser.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or any(not isinstance(payload.get(k), str) or not payload[k].strip() for k in REQUIRED):
        parser.error("Input must contain non-empty strings for: " + ", ".join(REQUIRED))
    if payload.get("data_authorization") != "authorized-real-data":
        parser.error("Refusing to analyze unverified input. Set data_authorization='authorized-real-data' only after confirming institutional authorization and provenance.")
    impacts = engine.analyze(payload["domain"], payload["change_variable"], payload["current_value"], payload["proposed_value"], payload["context"])
    report = {
        "input_source_reference": payload["source_reference"],
        "data_classification": "authorized real input supplied by operator; not independently verified by this script",
        "analysis_type": "rule-based hypotheses; not validated predictions",
        "impacts": impacts,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
