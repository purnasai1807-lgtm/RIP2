"""Acceptance checks for the bundled synthetic THE RIPPLE dataset engine."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "app" / "dataset_engine.py"
spec = importlib.util.spec_from_file_location("dataset_engine", MODULE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

def test_bundled_dataset_integrity():
    report = engine.validate_dataset()
    assert report["valid"], report["errors"]
    assert report["row_counts"]["activities"] == 35
    assert report["row_counts"]["services"] == 38
    assert report["row_counts"]["work_requests"] == 11

def test_v1_returns_causal_paths_and_limitations():
    result = engine.analyze_incident("V1")
    assert result["ok"]
    assert result["summary"]["initially_affected_services"] == 10
    assert result["services"]
    assert all(item["causal_path"] for item in result["services"])
    assert result["limitations"]

def test_variants_are_distinct():
    v1 = engine.analyze_incident("V1")
    v2 = engine.analyze_incident("V2")
    v3 = engine.analyze_incident("V3")
    assert v1["summary"]["initially_affected_services"] == 10
    assert v2["summary"]["initially_affected_services"] == 1
    assert "NET-CORE" in {s["service_id"] for s in v2["services"]}
    assert v3["summary"]["initially_affected_services"] == 4

def test_unknown_variant_is_rejected():
    try:
        engine.analyze_incident("V9")
    except ValueError:
        return
    assert False, "Unknown scenario variants must not be silently accepted"


def test_all_supplied_dataset_tables_are_loaded_and_reported():
    report = engine.dataset_report("V1")
    assert report["ok"]
    assert report["dataset"]["csv_tables_loaded"] == 19
    assert report["dataset"]["files_loaded"] == 20
    assert report["dataset"]["records_loaded"] == 567
    assert report["inventory"]["rooms"] == 26
    assert report["inventory"]["staff_directory"] == 62
    assert report["inventory"]["engineering_personnel"] == 30
    assert report["constraint_summary"]["hard"] > 0
    assert len(report["repair_jobs"]) == 11
    assert report["limitations"]

def test_dataset_report_variants_and_policy():
    v1 = engine.dataset_report("V1")
    v2 = engine.dataset_report("V2")
    v3 = engine.dataset_report("V3")
    assert v1["analysis"]["summary"]["initially_affected_services"] == 10
    assert v2["analysis"]["summary"]["initially_affected_services"] == 1
    assert v3["analysis"]["summary"]["initially_affected_services"] == 4
    assert v1["policy_summary"]["cancellation_allowed_activities"] == 10
    assert v1["policy_summary"]["cancellable_critical_or_mandatory_violations"] == []
