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
    if brief.get("constraints", {}).get("rig_required", True):
        add("rig", "rig_and_pose_test", [last])
        last = "rig"
    add("export", "export_and_reimport", [last])
    add("engine", "engine_import_and_animation_test", ["export"])
    graph = {"schema_version": 1, "brief": brief, "brief_hash": digest(brief),
             "nodes": nodes, "source_brief": snapshot(brief_path)}
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
    result["parent_ledger"] = snapshot(parent_path)
    result["revision_start"] = start
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("brief", type=Path)
    p.add_argument("ledger", type=Path)
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
                          "note": "Eligibility is dependency readiness, not backend availability."
                          }, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
