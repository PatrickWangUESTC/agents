#!/usr/bin/env python3
"""Prepare isolated task workspaces and optionally run Codex. Python 3.11+."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "workspace"
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def save_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def check_tree(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"Expected a real directory: {path}")
    for child in path.rglob("*"):
        if child.is_symlink() or not (child.is_dir() or child.is_file()):
            raise ValueError(f"Symlinks and special files are not supported: {child}")


def validate(template: Path = TEMPLATE) -> dict:
    check_tree(template)
    if not (template / "AGENTS.md").read_text().strip():
        raise ValueError("AGENTS.md is empty")
    with (template / ".codex/config.toml").open("rb") as f:
        tomllib.load(f)
    skills = []
    for path in sorted((template / ".agents/skills").glob("*/SKILL.md")):
        content = path.read_text()
        parts = content.split("---", 2)
        if len(parts) != 3 or parts[0].strip() or not parts[2].strip():
            raise ValueError(f"Missing frontmatter or body: {path}")
        # Bundled skills use simple, single-line YAML scalar metadata.
        metadata = dict(re.findall(r"^(name|description):\s*(.+)$", parts[1], re.M))
        if metadata.get("name") != path.parent.name or not metadata.get("description"):
            raise ValueError(f"Invalid skill name/description: {path}")
        skills.append(metadata["name"])
    roles = []
    for path in sorted((template / ".codex/agents").glob("*.toml")):
        with path.open("rb") as f:
            role = tomllib.load(f)
        for field in ("name", "description", "developer_instructions"):
            if not isinstance(role.get(field), str) or not role[field].strip():
                raise ValueError(f"Missing {field}: {path}")
        if role["name"] in roles:
            raise ValueError(f"Duplicate role: {role['name']}")
        roles.append(role["name"])
    if not skills or not roles:
        raise ValueError("Template needs skills and role definitions")
    return {"skills": skills, "roles": roles}


def prepare(destination: Path, input_dir: Path | None = None) -> Path:
    """Create a new workspace; never overlay or overwrite an existing directory."""
    validate()
    if destination.resolve().is_relative_to(TEMPLATE.resolve()):
        raise ValueError("Destination cannot be inside the workspace template")
    if input_dir is not None:
        check_tree(input_dir)
        if destination.resolve().is_relative_to(input_dir.resolve()):
            raise ValueError("Destination cannot be inside the input directory")
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    try:
        shutil.copytree(TEMPLATE, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("inputs", "artifacts", "work", ".git"))
        if input_dir is not None:
            shutil.copytree(input_dir, destination / "inputs")
        else:
            (destination / "inputs").mkdir()
        (destination / "artifacts").mkdir()
        (destination / "work").mkdir()
        # A repository boundary avoids loading instructions from a batch parent.
        subprocess.run(["git", "init", "-q", str(destination)], check=True,
                       capture_output=True, text=True)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination.resolve()


def load_tasks(manifest: Path) -> list[dict]:
    tasks = json.loads(manifest.read_text())
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Manifest must be a nonempty JSON array")
    seen = set()
    normalized = []
    for task in tasks:
        if not isinstance(task, dict) or set(task) - {"id", "prompt", "input"}:
            raise ValueError("Task must contain only id, prompt, and optional input")
        task_id, prompt = task.get("id"), task.get("prompt")
        if not isinstance(task_id, str) or not ID_PATTERN.fullmatch(task_id):
            raise ValueError(f"Invalid task id: {task_id!r}")
        if task_id in seen:
            raise ValueError(f"Duplicate task id: {task_id}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"Empty prompt: {task_id}")
        seen.add(task_id)
        input_dir = None
        if "input" in task:
            if not isinstance(task["input"], str) or not task["input"].strip():
                raise ValueError(f"Invalid input path: {task_id}")
            raw = manifest.parent / task["input"]
            check_tree(raw)
            input_dir = raw.resolve()
        normalized.append({"id": task_id, "prompt": prompt, "input": input_dir})
    return normalized


def command(binary: str, workspace: Path, result_dir: Path, model: str | None) -> list[str]:
    args = [binary, "exec", "-C", str(workspace), "--sandbox", "workspace-write",
            "-c", 'approval_policy="never"', "--json",
            "--output-last-message", str(result_dir / "final.md")]
    if model:
        args.extend(["--model", model])
    return args + ["-"]


def stop_process(process: subprocess.Popen) -> None:
    # Terminate the entire process group, including command children on POSIX.
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()
    process.wait()


def execute(task: dict, task_dir: Path, args: argparse.Namespace) -> dict:
    workspace = task_dir / "workspace"
    result_dir = task_dir / "result"
    result_dir.mkdir()
    (result_dir / "prompt.txt").write_text(task["prompt"])
    argv = command(args.codex_bin, workspace, result_dir, args.model)
    status = {"id": task["id"], "status": "prepared", "command": argv,
              "workspace": str(workspace), "acceptance": "unverified"}
    save_json(result_dir / "status.json", status)
    if not args.execute:
        return status
    status.update(status="running", started_at=time.time())
    save_json(result_dir / "status.json", status)
    process = None
    try:
        with (result_dir / "events.jsonl").open("w") as stdout, \
                (result_dir / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=stdout,
                                       stderr=stderr, text=True, cwd=workspace,
                                       start_new_session=(os.name == "posix"))
            try:
                process.communicate(task["prompt"], timeout=args.timeout)
                status["returncode"] = process.returncode
                final = result_dir / "final.md"
                if process.returncode == 0 and final.is_file() and final.stat().st_size:
                    status["status"] = "process_completed"
                else:
                    status.update(status="failed", error="Nonzero exit or missing final response")
            except subprocess.TimeoutExpired:
                stop_process(process)
                status.update(status="timed_out", error=f"Exceeded {args.timeout}s")
    except Exception as exc:
        if process is not None and process.poll() is None:
            stop_process(process)
        status.update(status="failed", error=str(exc))
    status["finished_at"] = time.time()
    save_json(result_dir / "status.json", status)
    return status


def launch(tasks: list[dict], destination: Path, args: argparse.Namespace) -> list[dict]:
    validate()
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(f"Run directory already exists: {destination}")
    for task in tasks:
        if task["input"] is not None and destination.is_relative_to(task["input"]):
            raise ValueError("Run directory cannot be inside an input directory")
    # Resolve executable before any tasks run; dry preparation needs no Codex install.
    if args.execute:
        binary = shutil.which(args.codex_bin)
        if binary is None:
            raise ValueError(f"Codex executable not found: {args.codex_bin}")
        args.codex_bin = str(Path(binary).resolve())
    destination.mkdir(parents=True)
    try:
        for task in tasks:
            prepare(destination / task["id"] / "workspace", task["input"])
    except BaseException:
        shutil.rmtree(destination)
        raise
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(execute, task, destination / task["id"], args) for task in tasks]
        results = [future.result() for future in futures]
    save_json(destination / "summary.json", results)
    return results


def positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("Must be positive")
    return result


def positive_seconds(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Must be finite and positive")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("validate", help="Validate bundled metadata and TOML; no model calls")
    init = sub.add_parser("init", help="Copy the template into a NEW directory")
    init.add_argument("destination", type=Path)
    init.add_argument("--input", type=Path)
    for name in ("run", "batch"):
        p = sub.add_parser(name, help="Prepare tasks; add --execute to call Codex")
        p.add_argument("--dest", required=True, type=Path, help="New run directory")
        p.add_argument("--execute", action="store_true")
        p.add_argument("--codex-bin", default="codex")
        p.add_argument("--model", help="Optional; otherwise inherit the user's configured model")
        p.add_argument("--timeout", type=positive_seconds, default=1800)
        if name == "run":
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("--prompt")
            group.add_argument("--prompt-file", type=Path)
            p.add_argument("--input", type=Path)
            p.set_defaults(jobs=1)
        else:
            p.add_argument("manifest", type=Path)
            p.add_argument("--jobs", type=positive_int, default=2)
    args = parser.parse_args()
    try:
        if args.action == "validate":
            print(json.dumps(validate(), ensure_ascii=False, indent=2))
        elif args.action == "init":
            print(prepare(args.destination.absolute(), args.input))
        else:
            if args.action == "batch":
                tasks = load_tasks(args.manifest.resolve())
            else:
                prompt = args.prompt_file.read_text() if args.prompt_file else args.prompt
                if not prompt.strip():
                    raise ValueError("Prompt cannot be empty")
                if args.input:
                    check_tree(args.input)
                tasks = [{"id": "task", "prompt": prompt,
                          "input": args.input.resolve() if args.input else None}]
            results = launch(tasks, args.dest, args)
            for result in results:
                print(f"{result['id']}: {result['status']} — {result['workspace']}")
            return int(any(r["status"] in {"failed", "timed_out"} for r in results))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
