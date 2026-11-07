#!/usr/bin/env python3
"""Character artifact ledger. Executes no model, provider API, or Blender command."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

VERDICTS = {"pass", "fail", "unknown", "not_run"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def snapshot(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Expected nonempty file: {path}")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def current(record):
    try:
        return snapshot(record["path"]) == record
    except (OSError, ValueError):
        return False


def write(path, value, new=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if new:
        with path.open("x") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
    else:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(path)


def initialize(brief_path, ledger_path):
    brief = json.loads(Path(brief_path).read_text())
    parts = brief.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("brief.parts must be a nonempty array")
    if any(not isinstance(p, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", p) for p in parts):
        raise ValueError("Part names must be lowercase identifiers")
    if len(parts) != len(set(parts)):
        raise ValueError("Part names must be unique")
    nodes = {}

    def add(name, operation, deps):
        nodes[name] = {"operation": operation, "deps": deps, "state": "pending"}

    add("reference", "inspect_reference", [])
    part_reference = "reference"
    if brief.get("reference_preparation", {}).get("apose_required", False):
        add("apose", "normalize_front_apose", ["reference"])
        part_reference = "apose"
    for part in parts:
        add("extract/" + part, "prepare_part_reference", [part_reference])
        add("generate/" + part, "generate_part", ["extract/" + part])
    add("assemble", "assemble", ["generate/" + p for p in parts])
    last = "assemble"
    if brief.get("constraints", {}).get("rig_required", False):
        add("rig", "rig_and_pose_test", [last])
        last = "rig"
    add("export", "export_and_reimport", [last])
    engine = brief.get("delivery", {}).get("engine", {})
    if engine.get("enabled", False):
        if not engine.get("target"):
            raise ValueError("Enabled engine validation needs a target")
        add("engine", "engine_import_and_animation_test", ["export"])
    graph = {"schema_version": 1, "brief": brief, "brief_hash": digest(brief),
             "nodes": nodes, "source_brief": snapshot(brief_path),
             "deferred": [] if "engine" in nodes else [{"node": "engine", "status": "not_run",
                 "reason": engine.get("reason", "Engine validation not requested")}]}
    write(ledger_path, graph, new=True)
    return graph


def continue_from_lab(brief_path, ledger_path, session_path):
    """Pin an existing Lab checkpoint; task acceptance is not asset acceptance."""
    ledger_path = Path(ledger_path).resolve()
    handoff_path = ledger_path.with_name(ledger_path.stem + "-handoff.json")
    if ledger_path.exists() or handoff_path.exists():
        raise FileExistsError("Use a new ledger and handoff path")
    brief = json.loads(Path(brief_path).read_text())
    delivery = brief.get("delivery", {})
    if delivery.get("facial_controls", False):
        raise ValueError("Facial controls require a separate explicit workflow")
    formats = delivery.get("formats", ["blend", "glb", "fbx"])
    if (not isinstance(formats, list) or not formats
            or any(f not in {"blend", "glb", "fbx"} for f in formats)):
        raise ValueError("delivery.formats must contain blend, glb or fbx")
    engine = delivery.get("engine", {})
    if engine.get("enabled", False) and not engine.get("target"):
        raise ValueError("Enabled engine validation needs a target")
    upgrade = brief.get("local_upgrade", {})
    if upgrade.get("enabled", False) and not (upgrade.get("part") and upgrade.get("reason")):
        raise ValueError("Optional local upgrade needs part and reason")
    session_path = Path(session_path).resolve(strict=True)
    session = json.loads((session_path / "session.json").read_text())
    revision = session["selected"]
    if not isinstance(revision, str) or not re.fullmatch(r"r[0-9]+", revision):
        raise ValueError("Invalid selected Lab revision")
    case = snapshot(session_path / "case.json")
    if case["sha256"] != session["case_sha256"]:
        raise ValueError("Lab case has changed")
    revdir = session_path / "revisions" / revision
    receipt_path = revdir / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("revision") != revision or receipt.get("status") != "produced":
        raise ValueError("Selected Lab revision was not successfully produced")
    files = receipt.get("files", {})
    for required in ("scene.blend", "inventory.json", "checks.json", "readback.json", "views.json"):
        if required not in files:
            raise ValueError(f"Missing Lab checkpoint file: {required}")
    pinned = [case, snapshot(receipt_path)]
    for relative, expected in files.items():
        path = (revdir / relative).resolve(strict=True)
        if not path.is_relative_to(revdir):
            raise ValueError("Lab receipt path escapes revision")
        observed = snapshot(path)
        if observed["sha256"] != expected:
            raise ValueError(f"Lab checkpoint changed: {relative}")
        pinned.append(observed)
    scene = snapshot(revdir / "scene.blend")
    nodes = {}

    def add(key, operation, deps, required):
        nodes[key] = {"operation": operation, "deps": deps, "state": "pending",
                      "required_checks": required,
                      "skills": {"lab_checkpoint": ["character-canvas"],
                                 "local_upgrade": ["character-part-upgrade"],
                                 "assembly_review": ["three-d-ai-lab"],
                                 "rig": ["character-rigging"],
                                 "pose_test": ["character-rigging"],
                                 "export": (["character-fbx-export", "character-delivery"] if "rig" in nodes else ["character-delivery"]),
                                 "roundtrip": (["character-fbx-export", "character-delivery"] if "rig" in nodes else ["character-delivery"]),
                                 "engine": ["character-delivery"]}[key]}

    add("lab_checkpoint", "pin_existing_lab_checkpoint", [], ["checkpoint_integrity"])
    last = "lab_checkpoint"
    if upgrade.get("enabled", False):
        add("local_upgrade", "extract_generate_replace_requested_part", [last],
            ["requested_part_replaced", "unaffected_parts_preserved", "visual_review"])
        last = "local_upgrade"
    add("assembly_review", "review_static_assembly", [last],
        ["part_inventory", "protected_properties", "four_view_review", "intersection_review"])
    last = "assembly_review"
    if brief.get("constraints", {}).get("rig_required", False):
        add("rig", "bind_current_parts_to_requested_skeleton", [last],
            ["all_parts_bound", "reference_skeleton", "normalized_weights", "rest_surface_preserved"])
        add("pose_test", "inspect_diagnostic_deformation", ["rig"],
            ["body_hair_deformation", "clothing_shoe_deformation", "posed_intersections"])
        last = "pose_test"
    add("export", "export_requested_formats", [last],
        ["requested_formats", "all_parts_exported", "materials_preserved"])
    add("roundtrip", "fresh_process_reimport", ["export"],
        ["parts_materials_dimensions", "skeleton_weights", "posed_surface_agreement"]
        if "rig" in nodes else ["parts_materials_dimensions", "static_surface_agreement"])
    deferred = []
    if engine.get("enabled", False):
        add("engine", "target_engine_import_and_motion_check", ["roundtrip"],
            ["target_engine_import", "target_engine_motion"])
    else:
        deferred.append({"node": "engine", "status": "not_run",
                         "reason": engine.get("reason", "Blender-only delivery; engine not requested")})
    graph = {"schema_version": 1, "workflow": "post_lab_v1", "brief": brief,
             "brief_hash": digest(brief), "source_brief": snapshot(brief_path),
             "nodes": nodes, "deferred": deferred,
             "handoff": {"session": str(session_path), "revision": revision, "scene": scene,
                         "lab_acceptance": receipt.get("acceptance", "not_run"),
                         "scope": "Checkpoint integrity only; assembly quality must be reviewed"}}
    evidence = {"scope": graph["handoff"]["scope"],
                "artifact_sha256": {scene["path"]: scene["sha256"]},
                "checks": [{"name": "checkpoint_integrity", "status": "pass",
                            "evidence": [r["path"] for r in pinned]}]}
    write(handoff_path, evidence, new=True)
    record(graph, "lab_checkpoint", [scene["path"]], handoff_path)
    write(ledger_path, graph, new=True)
    return graph


def load(path):
    graph = json.loads(Path(path).read_text())
    if graph.get("schema_version") != 1 or graph.get("brief_hash") != digest(graph["brief"]):
        raise ValueError("Unsupported or modified ledger brief; create a new ledger")
    return graph


def states(graph):
    result = {}
    visiting = set()

    def visit(key):
        if key in result:
            return result[key]
        if key in visiting:
            raise ValueError("Cyclic node dependencies")
        visiting.add(key)
        node = graph["nodes"][key]
        deps = {dep: visit(dep) for dep in node["deps"]}
        state = node["state"]
        if state in {"produced", "accepted"}:
            records = node["artifacts"] + [node["evidence"]] + node["evidence_files"]
            if (not all(current(r) for r in records)
                    or any(s != "accepted" for s in deps.values())
                    or node["dependency_signatures"] != {
                        dep: graph["nodes"][dep].get("signature") for dep in deps}):
                state = "stale"
        visiting.remove(key)
        result[key] = state
        return state

    for key in graph["nodes"]:
        visit(key)
    return result


def record(graph, key, artifacts, evidence_path):
    node = graph["nodes"][key]
    observed = states(graph)
    if node["state"] == "accepted":
        raise ValueError("Accepted nodes are immutable; fork a revision first")
    for dep in node["deps"]:
        if observed[dep] != "accepted":
            raise ValueError(f"Dependency not accepted/current: {dep}")
    evidence_path = Path(evidence_path).resolve()
    evidence = json.loads(evidence_path.read_text())
    if not isinstance(evidence.get("scope"), str) or not evidence["scope"].strip():
        raise ValueError("Evidence needs a scope")
    checks = evidence.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("Evidence needs nonempty checks")
    names = [check.get("name") for check in checks]
    if len(names) != len(set(names)):
        raise ValueError("Check names must be unique")
    missing = set(node.get("required_checks", [])) - set(names)
    if missing:
        raise ValueError(f"Missing required checks: {sorted(missing)}")
    files = []
    for check in checks:
        if (not isinstance(check.get("name"), str) or not check["name"].strip()
                or check.get("status") not in VERDICTS
                or not isinstance(check.get("evidence"), list) or not check["evidence"]):
            raise ValueError("Each check needs name, exact status, and evidence file paths")
        files.extend(snapshot(evidence_path.parent / p) for p in check["evidence"])
    if not artifacts:
        raise ValueError("At least one artifact is required")
    output_records = [snapshot(p) for p in artifacts]
    # Caller must explicitly bind evidence to the actual candidate, not just pass text.
    if evidence.get("artifact_sha256") != {r["path"]: r["sha256"] for r in output_records}:
        raise ValueError("Evidence artifact_sha256 must match absolute current artifact paths/hashes")
    verdicts = {check["status"] for check in checks}
    node.update(artifacts=output_records, evidence=snapshot(evidence_path),
                evidence_files=files, dependency_signatures={
                    dep: graph["nodes"][dep]["signature"] for dep in node["deps"]},
                state="accepted" if verdicts == {"pass"} else "produced")
    node.pop("reason", None)
    node["signature"] = digest({k: v for k, v in node.items() if k != "signature"})


def fork(graph, start, parent_path):
    if start not in graph["nodes"]:
        raise ValueError(f"Unknown node: {start}")
    result = copy.deepcopy(graph)
    dirty = {start}
    while True:
        descendants = {k for k, n in result["nodes"].items() if set(n["deps"]) & dirty}
        if descendants <= dirty:
            break
        dirty |= descendants
    for key in dirty:
        old = result["nodes"][key]
        result["nodes"][key] = {"operation": old["operation"], "deps": old["deps"],
                                "state": "pending"}
        for field in ("required_checks", "skills"):
            if field in old:
                result["nodes"][key][field] = copy.deepcopy(old[field])
    result["parent_ledger"] = snapshot(parent_path)
    result["revision_start"] = start
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("brief", type=Path)
    p.add_argument("ledger", type=Path)
    p = sub.add_parser("from-lab", help="Continue from a pinned existing Lab checkpoint")
    p.add_argument("brief", type=Path)
    p.add_argument("ledger", type=Path)
    p.add_argument("--session", required=True, type=Path)
    for name in ("status", "record", "block", "fork"):
        p = sub.add_parser(name)
        p.add_argument("ledger", type=Path)
        if name in {"record", "block"}:
            p.add_argument("node")
        if name == "record":
            p.add_argument("--artifact", action="append", required=True, type=Path)
            p.add_argument("--evidence", required=True, type=Path)
        if name == "block":
            p.add_argument("--reason", required=True)
            p.add_argument("--job-id", help="Existing provider job handle; not a new submission")
        if name == "fork":
            p.add_argument("--from-node", required=True)
            p.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            graph = initialize(args.brief, args.ledger)
        elif args.command == "from-lab":
            graph = continue_from_lab(args.brief, args.ledger, args.session)
        else:
            graph = load(args.ledger)
            if args.command == "record":
                record(graph, args.node, args.artifact, args.evidence)
                write(args.ledger, graph)
            elif args.command == "block":
                if graph["nodes"][args.node]["state"] == "accepted":
                    raise ValueError("Fork an accepted node before changing it")
                graph["nodes"][args.node].update(state="blocked", reason=args.reason,
                                                provider_job_id=args.job_id)
                write(args.ledger, graph)
            elif args.command == "fork":
                graph = fork(graph, args.from_node, args.ledger)
                write(args.out, graph, new=True)
        observed = states(graph)
        ready = [k for k, n in graph["nodes"].items()
                 if observed[k] in {"pending", "blocked", "stale", "produced"}
                 and all(observed[d] == "accepted" for d in n["deps"])]
        print(json.dumps({"states": observed, "eligible": ready,
                          "deferred": graph.get("deferred", []),
                          "note": "Eligibility is dependency readiness, not backend availability."
                          }, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
