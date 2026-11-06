#!/usr/bin/env python3
"""Resumable provider job -> original mesh. N4D adapter; standard library only."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import mimetypes
from pathlib import Path
import shutil
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

API = "https://alb.neural4d.com:3000/api"
DEFAULT_TOKEN = Path.home() / ".config/agents-providers/n4d.token"


def multipart(image, fields):
    image = Path(image)
    if image.stat().st_size >= 10 * 1024 * 1024:
        raise ValueError("N4D image upload must be smaller than 10 MiB")
    boundary = "n4d-" + uuid.uuid4().hex
    mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
             for k, v in fields.items()]
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="reference{image.suffix}"\r\n'
                  f'Content-Type: {mime}\r\n\r\n').encode() + image.read_bytes() + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), "multipart/form-data; boundary=" + boundary


def save(path, value, new=False):
    path = Path(path)
    if new:
        with path.open("x") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
    else:
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        temp.replace(path)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never redirect an authenticated provider request.


class N4D:
    name = "n4d"

    def __init__(self, token):
        self.token = token.strip()
        if not self.token:
            raise ValueError("Empty N4D credential")

    def request(self, endpoint, payload, content_type="application/json;charset=utf-8"):
        req = urllib.request.Request(API + "/" + endpoint,
            data=payload if isinstance(payload, bytes) else json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": content_type}, method="POST")
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not put credentials or unfiltered server bodies into logs.
            detail = ""
            try:
                body = json.loads(exc.read())
                errors = body.get("errors", [])
                detail = "; ".join(str(e.get("path", "")) + ": " + str(e.get("msg", ""))
                                   for e in errors if isinstance(e, dict))[:500]
                detail = detail.replace(self.token, "[REDACTED]")
            except (ValueError, AttributeError):
                pass
            raise RuntimeError(f"N4D HTTP {exc.code} at {endpoint}; no submission retry. {detail}") from None
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"N4D {type(exc).__name__} at {endpoint}; no submission retry") from None

    def balance(self):
        value = self.request("queryPointsInfo", {})
        if value.get("statusType") != 0:
            raise RuntimeError("N4D balance/authentication check failed")
        return value.get("data", {})

    def submit(self, prompt):
        response = self.request("generateModelWithText",
                                {"prompt": prompt, "modelCount": 1, "disablePbr": 1})
        uuids = response.get("uuids")
        if not isinstance(uuids, list) or len(uuids) != 1 or not isinstance(uuids[0], str):
            raise RuntimeError("Submission did not return exactly one UUID; reconcile account before retrying")
        return uuids[0]

    def matting(self, image):
        body, content_type = multipart(image, {})
        result = self.request("mattingImage", body, content_type)
        self.last_submission_response = self.submission_receipt(result)
        if result.get("requestId") is None:
            raise RuntimeError("Matting response has no requestId; reconcile before retrying: " +
                               json.dumps(self.last_submission_response, ensure_ascii=False))
        return result["requestId"]

    def matted(self, request_id):
        return self.request("getMattedResult", {"requestId": request_id})

    def submit_image(self, image):
        # Live API requires multipart image; the older PDF's fileKey JSON returns 400.
        body, content_type = multipart(image, {"modelCount": 1, "disablePbr": 1})
        result = self.request("generateModelWithImage", body, content_type)
        self.last_submission_response = self.submission_receipt(result)
        self.last_receipt = {k: result[k] for k in ("pointsDeducted", "generationConfig") if k in result}
        ids = result.get("uuids")
        if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str):
            raise RuntimeError("Image generation did not return exactly one UUID; reconcile before retrying: " +
                               json.dumps(self.last_submission_response, ensure_ascii=False))
        return ids[0]

    def submission_receipt(self, result):
        # Keep bounded diagnostic fields, not arbitrary provider payloads or secrets.
        allowed = ("type", "message", "statusType", "code", "requestId", "uuids", "pointsDeducted")
        safe = {k: result[k] for k in allowed if k in result}
        return json.loads(json.dumps(safe).replace(self.token, "[REDACTED]"))

    def poll(self, job_id):
        response = self.request("retrieveModel", {"uuid": job_id})
        code = response.get("codeStatus")
        if code == 0:
            url = response.get("modelUrl")
            if not isinstance(url, str) or not url:
                raise RuntimeError("Ready response has no modelUrl")
            return {"status": "ready", "model_url": url,
                    "preview_url": response.get("imageUrl")}
        if code == 1:
            return {"status": "running"}
        if code in {-1, -2, -3}:
            return {"status": "failed", "provider_code": code}
        raise RuntimeError(f"Unknown N4D status code: {code!r}")


def begin(out, prompt, provider):
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    job = {"schema_version": 1, "provider": provider.name, "status": "submitting",
           "request": {"input_mode": "text", "prompt": prompt, "model_count": 1, "pbr": False, "texture": "provider_default_unverified"},
           "native_lowpoly": "unverified", "acceptance": "unverified",
           "created_at": time.time()}
    save(out / "job.json", job, new=True)  # Persist BEFORE a potentially billable request.
    try:
        job["job_id"] = provider.submit(prompt)
        job["status"] = "submitted"
    except Exception:
        job["status"] = "submission_unknown"
        save(out / "job.json", job)
        raise
    save(out / "job.json", job)  # Store remote handle before polling.
    return job


def prepare_image(out, image, provider, timeout=120, interval=5):
    out, image = Path(out), Path(image)
    if not out.exists():
        out.mkdir(parents=True)
    state_path = out / "preprocess.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["image_sha256"] != hashlib.sha256(image.read_bytes()).hexdigest():
            raise ValueError("Different reference image; use a new output directory")
        if state["status"] == "matting_ready":
            if not state.get("matted_artifact"):
                state["matted_artifact"] = download(state["image_urls"][0], out / "matted.png")
                save(state_path, state)
            return state
        if not state.get("request_id"):
            raise ValueError("Uncertain matting submission; reconcile before retrying")
    else:
        target = out / ("reference" + image.suffix.lower())
        shutil.copyfile(image, target)
        state = {"provider": provider.name, "image_path": str(target.resolve()),
                 "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                 "status": "matting_submitting"}
        save(state_path, state, new=True)
        try:
            state["request_id"] = provider.matting(target)
        except Exception:
            state["submission_response"] = getattr(provider, "last_submission_response", {})
            save(state_path, state)
            raise
        state["status"] = "matting_running"
        save(state_path, state)
    deadline = time.monotonic() + timeout
    while True:
        result = provider.matted(state["request_id"])
        keys, urls = result.get("fileKeys"), result.get("mattedImageUrls")
        if isinstance(keys, list) and keys and isinstance(urls, list) and len(keys) == len(urls):
            state.update(status="matting_ready", file_keys=keys, image_urls=urls)
            save(state_path, state)
            state["matted_artifact"] = download(urls[0], out / "matted.png")
            save(state_path, state)
            return state
        if time.monotonic() >= deadline:
            raise TimeoutError("Matting wait timed out; repeat prepare-image to resume same request")
        time.sleep(interval)


def begin_image(out, provider, index=0):
    out = Path(out)
    prep = json.loads((out / "preprocess.json").read_text())
    if prep["status"] != "matting_ready":
        raise ValueError("Image preparation is not ready")
    if index != 0:
        raise ValueError("Only inspected first matting output is supported; prepare a new reference for alternatives")
    if hashlib.sha256(Path(prep["image_path"]).read_bytes()).hexdigest() != prep["image_sha256"]:
        raise ValueError("Reference image changed after preparation")
    job = {"schema_version": 1, "provider": provider.name, "status": "submitting",
           "request": {"input_mode": "image", "image_sha256": prep["image_sha256"],
                       "matting_request_id": prep["request_id"], "selected_index": index,
                       "model_count": 1, "pbr": False, "texture": "provider_default_unverified"},
           "native_lowpoly": "unverified", "acceptance": "unverified", "created_at": time.time()}
    wire_image = out / "matted.png"
    if not wire_image.is_file():
        raise ValueError("Missing matted.png; resume prepare-image first")
    if prep.get("matted_artifact") and hashlib.sha256(wire_image.read_bytes()).hexdigest() != prep["matted_artifact"]["sha256"]:
        raise ValueError("Matted reference changed")
    job["request"].update(wire_format="multipart/image", wire_image_sha256=hashlib.sha256(wire_image.read_bytes()).hexdigest())
    save(out / "job.json", job, new=True)
    try:
        job["job_id"] = provider.submit_image(wire_image)
        job["provider_receipt"] = getattr(provider, "last_receipt", {})
        job["status"] = "submitted"
    except Exception:
        job["status"] = "submission_unknown"
        job["submission_response"] = getattr(provider, "last_submission_response", {})
        save(out / "job.json", job)
        raise
    save(out / "job.json", job)
    return job


def download(url, path):
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("Artifact downloads require HTTPS")
    temp = path.with_suffix(path.suffix + ".partial")
    try:
        # No provider authorization header is sent to asset storage.
        with urllib.request.urlopen(url, timeout=120) as response, temp.open("xb") as f:
            total = 0
            while data := response.read(1024 * 1024):
                total += len(data)
                if total > 512 * 1024 * 1024:
                    raise ValueError("Artifact exceeds 512 MiB download limit")
                f.write(data)
        if total == 0:
            raise ValueError("Empty artifact")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def resume(out, provider, timeout=600, interval=10, downloader=download):
    out = Path(out)
    job = json.loads((out / "job.json").read_text())
    if job["provider"] != provider.name:
        raise ValueError("Provider must match saved job")
    if job["status"] in {"submitting", "submission_unknown"} or not job.get("job_id"):
        raise ValueError("Submission outcome uncertain. Reconcile account; do not submit again")
    if job["status"] == "downloaded":
        artifact = job["artifact"]
        path = Path(artifact["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("Downloaded source changed; restore it before resuming")
        return job
    if job["status"] == "failed":
        raise ValueError("Provider marked this job failed; no automatic resubmission")
    deadline = time.monotonic() + timeout
    while True:
        try:
            observed = provider.poll(job["job_id"])
        except Exception:
            job["status"] = "poll_error"
            save(out / "job.json", job)
            raise
        job.update(observed)
        job["updated_at"] = time.time()
        save(out / "job.json", job)
        if job["status"] == "failed":
            raise RuntimeError(f"N4D generation failed with code {job.get('provider_code')}")
        if job["status"] == "ready":
            suffix = Path(urllib.parse.urlparse(job["model_url"]).path).suffix.lower()
            if suffix not in {".glb", ".gltf", ".obj", ".fbx", ".zip"}:
                raise ValueError("Unknown output format; inspect provider result before downloading")
            path = out / ("source" + suffix)
            try:
                job["artifact"] = downloader(job["model_url"], path)
            except Exception:
                job["status"] = "download_error"
                save(out / "job.json", job)
                raise
            job["status"] = "downloaded"
            save(out / "job.json", job)
            return job
        if time.monotonic() >= deadline:
            job["status"] = "waiting_timeout"
            save(out / "job.json", job)
            return job
        time.sleep(min(interval, max(0, deadline - time.monotonic())))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["balance", "generate", "prepare-image", "generate-image", "resume"])
    p.add_argument("--provider", choices=["n4d"], default="n4d")
    p.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN)
    p.add_argument("--prompt-file", type=Path)
    p.add_argument("--image", type=Path)
    p.add_argument("--image-index", type=int, default=0)
    p.add_argument("--out", type=Path)
    p.add_argument("--execute", action="store_true", help="Authorize a single new generation submission")
    p.add_argument("--timeout", type=float, default=600)
    p.add_argument("--interval", type=float, default=10)
    args = p.parse_args()
    try:
        if not 0 < args.timeout < float('inf') or not 1 <= args.interval < float('inf'):
            raise ValueError("Timeout must be finite and positive; interval must be finite and >=1s")
        if args.action == "generate":
            if args.prompt_file is None or args.out is None:
                raise ValueError("generate requires --prompt-file and --out")
            prompt = args.prompt_file.read_text()
            if not args.execute:
                print(json.dumps({"provider": args.provider, "prompt": prompt,
                    "model_count": 1, "pbr": False, "texture": "provider_default_unverified", "submitted": False,
                    "native_lowpoly": "unverified", "postprocess_target_triangles": None}, indent=2))
                return 0
        elif args.action in {"resume", "prepare-image", "generate-image"} and args.out is None:
            raise ValueError("resume requires --out")
        if args.action in {"prepare-image", "generate-image"} and not args.execute:
            raise ValueError("Image upload/generation requires --execute")
        if args.action == "prepare-image" and args.image is None:
            raise ValueError("prepare-image requires --image")
        token = os.environ.get("N4D_API_TOKEN") or args.token_file.read_text().strip()
        provider = N4D(token)
        if args.action == "balance":
            print(json.dumps(provider.balance(), ensure_ascii=False, indent=2))
            return 0
        if args.action == "generate":
            begin(args.out, prompt, provider)
        elif args.action == "prepare-image":
            value = prepare_image(args.out, args.image, provider, args.timeout, args.interval)
            print(json.dumps({"status": value["status"], "request_id": value["request_id"],
                              "candidates": len(value["file_keys"])}, indent=2))
            return 0
        elif args.action == "generate-image":
            begin_image(args.out, provider, args.image_index)
        result = resume(args.out, provider, args.timeout, args.interval)
        print(json.dumps({k: result.get(k) for k in ("provider", "job_id", "status", "artifact", "acceptance")}, indent=2))
        return 0 if result["status"] == "downloaded" else 1
    except Exception as exc:
        # Deliberately do not print traceback or token-bearing HTTP internals.
        message = str(exc)
        secret = locals().get("token", "")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        print(json.dumps({"error": message, "exception": type(exc).__name__}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
