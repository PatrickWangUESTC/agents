"""Check final skirt contact samples from a reopened action."""
import argparse
import csv
import json
import math
from pathlib import Path


def check(rows, first, last, subdivisions, path_count=None):
    if subdivisions < 2 or last <= first:
        raise ValueError("Expected an action interval with subframe samples")
    failures = {}
    count = 0
    for index, row in enumerate(rows):
        frame, leg, footwear = (
            float(row[key]) for key in
            ("frame", "skirt-leg", "skirt-footwear")
        )
        if not all(map(math.isfinite, (frame, leg, footwear))):
            raise ValueError("Nonfinite sample at row " + str(index + 1))
        if abs(frame - (first + index / subdivisions)) > 1e-7:
            raise ValueError("Missing or out-of-order sample at row " + str(index + 1))
        if min(leg, footwear) < 0 or not leg.is_integer() or not footwear.is_integer():
            raise ValueError("Invalid intersection count at frame " + str(frame))
        for key, failed in (("skirt_leg", leg > 0), ("skirt_footwear", footwear > 0)):
            if failed:
                record = failures.setdefault(key, {"samples": 0, "first_frame": frame})
                record["samples"] += 1
        count += 1
    if count != (last - first) * subdivisions + 1:
        failures["incomplete_interval"] = True
    return {"skirt_numeric_passed": not failures, "samples": count, "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    for field in ("first", "last", "subdivisions"):
        parser.add_argument("--" + field, type=int, required=True)
    parser.add_argument("--paths", type=int, help=argparse.SUPPRESS)  # Legacy callers
    args = parser.parse_args()
    with args.samples.open(newline="") as stream:
        result = check(csv.DictReader(stream), args.first, args.last, args.subdivisions, args.paths)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["skirt_numeric_passed"] else 1)
