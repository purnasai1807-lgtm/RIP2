"""Dataset-backed analysis for the supplied THE RIPPLE campus crisis package.

The package is synthetic teaching data. This module never silently substitutes demo
records for missing records and does not claim to certify an optimized timetable.
"""
from __future__ import annotations
import csv
import json
from collections import defaultdict, deque
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "ripple_dataset"

TABLES = (
    "activities", "activity_modes", "buildings", "constraints", "dependencies",
    "engineering_personnel", "facility_contacts", "parts", "room_availability",
    "room_features", "room_services", "rooms", "service_links",
    "service_repair_map", "services", "staff_assignments", "staff_directory",
    "staff_roles", "work_requests",
)

def _read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def load_dataset(data_dir: Path | str = DATA_DIR):
    root = Path(data_dir)
    missing = [name for name in TABLES if not (root / f"{name}.csv").is_file()]
    if not (root / "incident.json").is_file():
        missing.append("incident.json")
    if missing:
        raise FileNotFoundError("Dataset is incomplete; missing: " + ", ".join(missing))
    tables = {name: _read_csv(root / f"{name}.csv") for name in TABLES}
    incident = json.loads((root / "incident.json").read_text(encoding="utf-8"))
    return {"tables": tables, "incident": incident, "data_dir": str(root)}

def validate_dataset(dataset=None, data_dir: Path | str = DATA_DIR):
    ds = dataset or load_dataset(data_dir)
    t = ds["tables"]
    errors, warnings = [], []
    # Primary keys and references used by the dependency and impact engines.
    def unique(table, key):
        vals = [r.get(key, "").strip() for r in t[table]]
        duplicates = sorted({v for v in vals if v and vals.count(v) > 1})
        if duplicates:
            errors.append(f"{table}.{key} has duplicate IDs: {', '.join(duplicates[:10])}")
        if any(not v for v in vals):
            errors.append(f"{table}.{key} contains blank IDs")
        return set(vals)
    service_ids = unique("services", "service_id")
    room_ids = unique("rooms", "room_id")
    activity_ids = unique("activities", "activity_id")
    unique("buildings", "building_id")
    unique("work_requests", "request_id")
    for row in t["service_links"]:
        for col in ("source_service", "target_service"):
            if row.get(col) not in service_ids:
                errors.append(f"service_links references unknown {col}={row.get(col)!r}")
    for row in t["room_services"]:
        if row.get("room_id") not in room_ids or row.get("service_id") not in service_ids:
            errors.append(f"room_services has invalid room/service reference: {row}")
    for row in t["dependencies"]:
        for col in ("source_activity", "target_activity"):
            if row.get(col) not in activity_ids:
                errors.append(f"dependencies references unknown {col}={row.get(col)!r}")
    for row in t["activities"]:
        if row.get("original_room_id") not in room_ids:
            errors.append(f"activity {row.get('activity_id')} references unknown room {row.get('original_room_id')}")
    for row in t["service_repair_map"]:
        if row.get("target_service_id") not in service_ids:
            errors.append(f"service_repair_map references unknown service {row.get('target_service_id')}")
    for row in t["work_requests"]:
        if row.get("prerequisite_request_id") and row["prerequisite_request_id"] not in {x["request_id"] for x in t["work_requests"]}:
            errors.append(f"work request {row.get('request_id')} has unknown prerequisite")
    if len(t["activities"]) == 0 or len(t["services"]) == 0:
        errors.append("Activities and services must not be empty")
    if any(not r.get("initial_state") for r in t["services"]):
        warnings.append("Some service states are missing; these must be treated as unknown, not healthy.")
    return {
        "valid": not errors, "errors": errors, "warnings": warnings,
        "row_counts": {name: len(rows) for name, rows in t.items()},
        "incident_id": ds["incident"].get("incident_id"),
        "scenario_name": ds["incident"].get("scenario_name"),
        "dataset_version": "2.2-cancellation-policy-audited",
    }

def _split(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]

def analyze_incident(variant_id: str = "V1", data_dir: Path | str = DATA_DIR):
    ds = load_dataset(data_dir)
    validation = validate_dataset(ds)
    if not validation["valid"]:
        return {"ok": False, "validation": validation, "error": "Dataset validation failed; impact analysis stopped."}
    t, incident = ds["tables"], ds["incident"]
    variant = next((v for v in incident.get("scenario_variants", []) if v.get("variant_id") == variant_id), None)
    if not variant:
        raise ValueError(f"Unknown scenario variant: {variant_id}")
    if variant_id == "V1":
        failed = set(incident.get("affected_service_ids", []))
    elif variant_id == "V2":
        # The variant states that the backbone is the only initial fault;
        # downstream branches are discovered through service_links.
        failed = {"NET-CORE"}
    elif variant_id == "V3":
        # Restrict initial water failure to the canteen service; do not mark
        # every water service on campus as failed.
        failed = {sid for sid in incident.get("affected_service_ids", [])
                  if sid.startswith("PWR-") or sid == "WAT-CAN"}
    else:
        failed = set(incident.get("affected_service_ids", []))
    services = {r["service_id"]: r for r in t["services"]}
    links = defaultdict(list)
    for edge in t["service_links"]:
        # Source is the upstream prerequisite; its failure can affect the target.
        links[edge["source_service"]].append(edge["target_service"])
    # Traverse service dependency graph and retain causal paths; cycle-safe.
    service_paths = {}
    queue = deque((sid, [sid]) for sid in sorted(failed) if sid in services)
    for sid in failed:
        if sid not in services:
            validation["warnings"].append(f"Incident references unknown service {sid}; not traversed.")
    while queue:
        current, path = queue.popleft()
        if current in service_paths and len(service_paths[current]) <= len(path):
            continue
        service_paths[current] = path
        for nxt in links.get(current, []):
            if nxt not in path:
                queue.append((nxt, path + [nxt]))
    room_services = defaultdict(list)
    for row in t["room_services"]:
        room_services[row["room_id"]].append(row)
    rooms = {r["room_id"]: r for r in t["rooms"]}
    activities_out = []
    impacted_room_ids = set()
    for activity in t["activities"]:
        room_id = activity.get("original_room_id")
        room = rooms.get(room_id, {})
        required_types = set(_split(activity.get("required_service_types")))
        relevant = []
        for link in room_services.get(room_id, []):
            service = services.get(link["service_id"], {})
            state = service.get("initial_state", "").strip().lower() or "unknown"
            is_required = link.get("required_for_normal_operation", "").lower() == "true"
            if link["service_id"] in service_paths and (is_required or link.get("service_type") in required_types):
                relevant.append({
                    "service_id": link["service_id"], "service_type": link.get("service_type"),
                    "state": state, "causal_path": service_paths[link["service_id"]],
                    "required_for_normal_operation": is_required,
                })
        if relevant:
            impacted_room_ids.add(room_id)
            activities_out.append({
                "activity_id": activity["activity_id"], "activity_name": activity["activity_name"],
                "original_room_id": room_id, "original_start": activity.get("original_start"),
                "original_end": activity.get("original_end"), "priority": activity.get("priority"),
                "cancellation_allowed": activity.get("cancellation_allowed", "").lower() == "true",
                "required_service_types": sorted(required_types), "blocking_or_risk_services": relevant,
                "impact_status": "potentially_disrupted",
                "note": "This is a dataset-backed dependency flag, not a certified rescheduling decision.",
            })
    service_results = []
    for sid, path in sorted(service_paths.items()):
        service = services[sid]
        service_results.append({
            "service_id": sid, "service_type": service.get("service_type"),
            "location_id": service.get("location_id"), "initial_state": service.get("initial_state") or "unknown",
            "safety_critical": service.get("safety_critical", "").lower() == "true",
            "causal_path": path,
            "is_initial_incident": sid in failed,
        })
    hard_dependencies = [r for r in t["dependencies"] if r.get("constraint_type", "").lower() == "hard"]
    soft_dependencies = [r for r in t["dependencies"] if r.get("constraint_type", "").lower() == "soft"]
    impacted_activity_ids = {r["activity_id"] for r in activities_out}
    downstream_activity_edges = []
    changed = True
    while changed:
        changed = False
        for edge in hard_dependencies:
            if edge["source_activity"] in impacted_activity_ids and edge["target_activity"] not in impacted_activity_ids:
                impacted_activity_ids.add(edge["target_activity"]); changed = True
                downstream_activity_edges.append(edge)
            elif edge["target_activity"] in impacted_activity_ids and edge["source_activity"] not in impacted_activity_ids:
                # Do not mark prerequisites as impacted solely due to a downstream activity.
                pass
    by_id = {r["activity_id"]: r for r in t["activities"]}
    existing = {r["activity_id"] for r in activities_out}
    for aid in sorted(impacted_activity_ids - existing):
        a = by_id[aid]
        activities_out.append({
            "activity_id": aid, "activity_name": a.get("activity_name"),
            "original_room_id": a.get("original_room_id"), "original_start": a.get("original_start"),
            "original_end": a.get("original_end"), "priority": a.get("priority"),
            "cancellation_allowed": a.get("cancellation_allowed", "").lower() == "true",
            "required_service_types": _split(a.get("required_service_types")),
            "blocking_or_risk_services": [], "impact_status": "downstream_hard_dependency",
            "note": "Included because a hard activity dependency links it to an already impacted activity; validate exact timing before acting.",
        })
    return {
        "ok": True, "validation": validation, "scenario": {"variant_id": variant_id,
        "description": variant.get("description"), "incident_start": incident.get("incident_start"),
        "simulation_start": incident.get("simulation_start"), "simulation_end": incident.get("simulation_end")},
        "summary": {"initially_affected_services": len(failed), "services_in_dependency_closure": len(service_results),
                    "potentially_disrupted_activities": len(activities_out), "rooms_with_service_risks": len(impacted_room_ids),
                    "hard_activity_dependencies": len(hard_dependencies), "soft_activity_dependencies": len(soft_dependencies),
                    "work_requests_available": len(t["work_requests"]), "activities_total": len(t["activities"])},
        "services": service_results,
        "activities": sorted(activities_out, key=lambda x: (x.get("original_start") or "", x.get("activity_id") or "")),
        "data_provenance": "Synthetic THE RIPPLE dataset v2.2; results are computed from supplied CSV/JSON files.",
        "limitations": [
            "This release computes dependency-based impact flags; it does not yet solve or certify a complete revised timetable.",
            "Service restoration times are not guessed. Work requests require qualified staff, prerequisites, parts, work duration and verification.",
            "The supplied package is synthetic teaching data, not verified live ACE Engineering College operational data.",
        ],
    }
