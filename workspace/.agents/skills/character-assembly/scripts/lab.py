#!/usr/bin/env python3
"""Local, auditable assembly executor. The calling agent plans and reviews.

python lab.py CONFIG.json --out NEW_REVISION --blender /path/to/blender
No provider calls, subscription dependency, automatic acceptance or file overwrite.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vector(value, size=3, positive=False):
    if not isinstance(value, list) or len(value) != size or any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
        or (positive and x <= 0) for x in value
    ):
        raise ValueError(f"Expected {size} finite numbers: {value!r}")
    return value


def prepare(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text())
    if config.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if not str(config.get("instruction", "")).strip():
        raise ValueError("Record the assembly instruction")
    parts = config.get("parts", [])
    if len(parts) < 2:
        raise ValueError("Assembly requires at least two supplied parts")
    names = set()
    for part in parts:
        name = part.get("name", "")
        if not name or not all(c.isalnum() or c in "_-" for c in name) or name in names:
            raise ValueError("Part names must be unique simple identifiers")
        names.add(name)
        source = (path.parent / part["source"]).resolve()
        if source.suffix.lower() != ".glb" or not source.is_file():
            raise ValueError(f"Missing GLB input: {source}")
        part["source"] = str(source)
        expected = part.get("source_sha256")
        actual = digest(source)
        if expected and expected != actual:
            raise ValueError(f"Changed input: {name}")
        part["source_sha256"] = actual
        vector(part.setdefault("scale", [1, 1, 1]), positive=True)
        vector(part.setdefault("translation", [0, 0, 0]))
        vector(part.setdefault("rotation_degrees", [0, 0, 0]))
        # Explicit optional z-dependent fit. The body is normally protected.
        profile = part.get("fit_profile", [])
        if profile and part.get("protected_geometry", False):
            raise ValueError("Cannot deform protected geometry")
        for row in profile:
            vector(row, 5)
            if row[1] <= 0 or row[2] <= 0:
                raise ValueError("Profile x/y scales must be positive")
        if any(b[0] <= a[0] for a, b in zip(profile, profile[1:])):
            raise ValueError("Fit profile heights must strictly increase")
        for edit in part.get('local_offsets', []):
            if part.get('protected_geometry'):
                raise ValueError('Cannot deform protected geometry')
            vector(edit['center'])
            vector(edit['radius'], positive=True)
            vector(edit['delta'])
    reference = (path.parent / config["reference"]).resolve()
    if not reference.is_file():
        raise ValueError("Missing reference")
    config["reference"] = str(reference)
    config["reference_sha256"] = digest(reference)
    for part in parts:
        contact = part.get("surface_clearance")
        if contact:
            if part.get("protected_geometry") or contact.get("target") not in names or contact['target'] == part['name']:
                raise ValueError("Clearance needs a different supplied target and unprotected editable part")
            for key in ('margin', 'max_displacement'):
                vector([contact[key]], 1, positive=True)
            if contact.get('iterations', 2) not in (1, 2, 3):
                raise ValueError('Use 1 to 3 clearance iterations')
            if contact.get('target_filter') not in (None, 'neutral_albedo'):
                raise ValueError('Unknown collider filter')
            if contact.get('target_filter') == 'neutral_albedo':
                vector([contact['max_channel_ratio']], 1, positive=True)
            if 'smoothing_cell' in contact:
                vector([contact['smoothing_cell']], 1, positive=True)
    height = config.get("display_height_m", 1.65)
    if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or height <= 0:
        raise ValueError("display_height_m must be positive and finite")
    config["display_height_m"] = height
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--blender", default=shutil.which("blender"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    config = prepare(args.config)
    if args.validate_only:
        print(json.dumps({"validated": True, "parts": [p["name"] for p in config["parts"]]}))
        return
    if not args.blender or not Path(args.blender).is_file():
        parser.error("Supply --blender with an installed Blender executable")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    effective = out / "config.json"
    effective.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    worker = Path(__file__).with_name("assemble_blender.py")
    shutil.copy2(worker, out / "assemble_blender.py")
    shutil.copy2(Path(__file__), out / "lab.py")
    state = {"status": "running", "started": time.time(), "config_sha256": digest(effective),
             "worker_sha256": digest(worker), "acceptance": "not_run"}
    statefile = out / "run.json"
    statefile.write_text(json.dumps(state, indent=2) + "\n")
    try:
        with (out / "execution.log").open("w") as log:
            result = subprocess.run([args.blender, "--background", "--factory-startup",
                "--python-exit-code", "1", "--python", str(out / worker.name), "--", str(effective)],
                stdout=log, stderr=subprocess.STDOUT)
    except OSError as exc:
        state.update(status='failed', error=str(exc), finished=time.time())
        statefile.write_text(json.dumps(state, indent=2) + '\n')
        raise
    state.update(status="produced" if result.returncode == 0 else "failed",
                 exit_code=result.returncode, finished=time.time())
    statefile.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
