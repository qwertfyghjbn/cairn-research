"""Launch a Cairn competition run, take checkpoints, and seal the evidence."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import tarfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASELINE = "8e7e0ea67552383851dfcabfba0c4e9c8d007878"
WORKER = "ghcr.io/oritera/cairn-worker-container@sha256:d90d40b7c634b8d5dc9464e04b863a185b9efe964ffd2b246f6e5cbc2a2ef053"
BASE_IMAGE = "ghcr.io/astral-sh/uv@sha256:c11a6b0892dcaafa4adfe89cc680117c955a8c55b107c2d432cee069b006cad8"
RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}\Z")
PROJECT_ID = re.compile(r"proj_\d+\Z")


def now():
    return datetime.now(timezone.utc).isoformat()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def save(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load(path):
    return json.loads(path.read_bytes())


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def project_id(value):
    if not PROJECT_ID.fullmatch(value):
        raise argparse.ArgumentTypeError("expected a Cairn project ID such as proj_001")
    return value


class Competition:
    def __init__(self, run_id):
        if not RUN_ID.fullmatch(run_id):
            raise ValueError("run ID must use 1–40 lowercase letters, digits or hyphens")
        self.run_id = run_id
        self.directory = HERE / "runs" / run_id
        self.evidence = self.directory / "evidence"

    def manifest(self):
        return load(self.evidence / "manifest.json")

    def compose(self, *args, **kwargs):
        manifest = self.manifest()
        env = {**os.environ, "CTF_RUN_ID": self.run_id, "CTF_PORT": str(manifest["server_port"]),
               "CTF_RUN_DIR": self.directory.as_posix(), "CTF_MODEL_URL": manifest["model_url"]}
        command = ["docker", "compose", "-f", str(self.evidence / "compose.yaml")]
        if manifest["fixture"]:
            command.extend(["-f", str(self.evidence / "fixture.yaml")])
        return run([*command, "-p", f"cairn-ctf-{self.run_id}", *args], env=env, **kwargs)

    def api(self, path, *, method="GET", payload=None):
        url = f"http://127.0.0.1:{self.manifest()['server_port']}{path}"
        body = json.dumps(payload).encode() if payload is not None else None
        with urlopen(Request(url, data=body, method=method, headers={"Content-Type": "application/json"}),
                     timeout=10) as response:
            return response.read()

    def init(self, args):
        if args.fixture:
            args.model_url = "http://fixture:8090"
        target = urlsplit(args.model_url)
        if (target.scheme not in {"https", "http"} or not target.hostname
                or target.username or target.query or target.fragment):
            raise ValueError("model URL must be an HTTP(S) API base URL without credentials or query")
        if min(args.workers, args.context_window) < 1 or not 1 <= args.port <= 65535:
            raise ValueError("workers and context window must be positive, port must be between 1 and 65535")
        self.directory.mkdir(mode=0o700, parents=True)
        for name in ("dispatcher", "model", "submissions", "checkpoints"):
            (self.evidence / name).mkdir(parents=True)
        (self.directory / "state").mkdir()
        # Use committed upstream bytes, including its dependency lock and default prompts.
        archive = run(["git", "archive", BASELINE], cwd=ROOT, stdout=subprocess.PIPE).stdout
        upstream = self.directory / "upstream"
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(upstream, filter="data")
        dockerfile = (upstream / "Dockerfile").read_bytes()
        original = b"FROM ghcr.io/astral-sh/uv:python3.13-trixie"
        if not dockerfile.startswith(original):
            raise ValueError("unexpected upstream Dockerfile base image")
        (self.directory / "Dockerfile").write_bytes(dockerfile.replace(original, f"FROM {BASE_IMAGE}".encode(), 1))
        names = ["compose.yaml", "observe.py", "model_recorder.py", "competition.py", "review.py"]
        if args.fixture:
            names.extend(["fixture.yaml", "fixture.py", "m4f1-project.json"])
            (self.evidence / "m4f1.py").write_bytes((ROOT / "m4f1/server.py").read_bytes())
        for name in names:
            (self.evidence / name).write_bytes((HERE / name).read_bytes())
        (self.evidence / "build.Dockerfile").write_bytes((self.directory / "Dockerfile").read_bytes())
        tokens = {secrets.token_urlsafe(32): f"pi-{index:03d}" for index in range(1, args.workers + 1)}
        save(self.directory / "model-clients.json", tokens)
        config = {
            "server": "http://server:8000",
            "runtime": {"interval": 3, "max_workers": args.workers, "max_running_projects": args.workers,
                        "max_project_workers": args.workers, "healthcheck_timeout": 20,
                        "worker_healthcheck": "startup_only", "prompt_group": "default"},
            "tasks": {"bootstrap": {"timeout": 300, "conclude_timeout": 90},
                      "reason": {"timeout": 300, "max_intents": 2},
                      "explore": {"timeout": 300, "conclude_timeout": 90}},
            "container": {"image": WORKER, "network_mode": f"cairn-ctf-{self.run_id}-workers",
                          "completed_action": "stop"},
            "workers": [{"name": name, "type": "pi", "task_types": ["bootstrap", "reason", "explore"],
                         "max_running": 1, "priority": 0,
                         "env": {"PI_MODEL": args.model, "PI_BASE_URL": "http://model-recorder:8080",
                                 "PI_API_KEY": token, "PI_PROVIDER_API": "openai-completions",
                                 "PI_MODEL_CONTEXT_WINDOW": str(args.context_window)}}
                        for token, name in tokens.items()],
        }
        save(self.directory / "dispatch.json", config)
        for worker in config["workers"]:
            worker["env"]["PI_API_KEY"] = "[REDACTED]"
        save(self.evidence / "dispatch.json", config)
        prompts = upstream / "cairn/src/cairn/dispatcher/prompts/default"
        save(self.evidence / "manifest.json", {
            "format": "cairn-ctf-1", "run_id": self.run_id, "created_at": now(), "upstream_commit": BASELINE,
            "worker_image": WORKER, "app_base_image": BASE_IMAGE, "platform": "linux/amd64",
            "uv_lock_sha256": checksum(upstream / "cairn/uv.lock"),
            "prompts": {path.name: checksum(path) for path in sorted(prompts.glob("*.md"))},
            "model": args.model, "model_url": args.model_url, "server_port": args.port,
            "container_prefix": f"cairn-ctf-{self.run_id}-", "fixture": args.fixture,
        })
        print(self.directory)

    def start(self):
        self.require_unsealed()
        if not self.manifest()["fixture"] and not os.environ.get("CTF_PROVIDER_KEY"):
            raise ValueError("set CTF_PROVIDER_KEY in the environment before starting")
        if self.manifest()["fixture"] and os.environ.get("CTF_PROVIDER_KEY"):
            raise ValueError("unset CTF_PROVIDER_KEY before starting a fixture")
        engine = run(["docker", "info", "--format", "{{.OSType}}"], capture_output=True, text=True)
        if engine.stdout.strip() != "linux":
            raise ValueError("a Linux Docker engine is required")
        self.compose("up", "-d", "--build", "--wait", "--wait-timeout", "120")
        image = run(["docker", "image", "inspect", "--format", "{{.Id}}", f"cairn-ctf-{self.run_id}"],
                    capture_output=True, text=True).stdout.strip()
        starts = self.evidence / "starts.jsonl"
        with starts.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"timestamp": now(), "app_image_id": image}) + "\n")

    def require_unsealed(self):
        if (self.evidence / "index.json").exists():
            raise ValueError("run evidence has been sealed")

    def new_project(self, spec):
        self.require_unsealed()
        payload = load(spec)
        created = json.loads(self.api("/projects", method="POST", payload=payload))
        project = project_id(created["project"]["id"])
        directory = self.evidence / "projects" / project
        directory.mkdir(parents=True, exist_ok=True)
        save(directory / "input.json", payload)
        save(directory / "created.json", created)
        print(project)

    def stop_project(self, project):
        self.require_unsealed()
        self.api(f"/projects/{project}/status", method="PUT", payload={"status": "stopped"})

    def submission(self, project, receipt):
        self.require_unsealed()
        payload = load(receipt)
        if not isinstance(payload, dict) or not isinstance(payload.get("accepted"), bool):
            raise ValueError("receipt must be a JSON object with an accepted boolean")
        timestamp = payload.get("submitted_at")
        if timestamp is not None and (not isinstance(timestamp, str) or datetime.fromisoformat(timestamp).tzinfo is None):
            raise ValueError("submitted_at must be an ISO 8601 timestamp with a timezone")
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        save(self.evidence / "submissions" / f"{project}-{name}.json",
             {"project_id": project, "recorded_at": now(), "receipt": payload})

    def snapshot(self, directory):
        source = self.directory / "state" / "cairn.db"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as src:
            with closing(sqlite3.connect(directory / "cairn.db")) as dst:
                deadline = time.monotonic() + 15

                def progress(_status, _remaining, _total):
                    if time.monotonic() > deadline:
                        raise TimeoutError("SQLite snapshot did not settle in 15 seconds")

                src.backup(dst, pages=64, progress=progress, sleep=0.1)
                if dst.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise ValueError("SQLite snapshot failed quick_check")
                return dst.execute("SELECT id, status FROM projects ORDER BY id").fetchall()

    def collect(self, final=False):
        self.require_unsealed()
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory = self.evidence / "checkpoints" / name
        directory.mkdir()
        gaps = []
        try:
            projects = self.snapshot(directory)
        except (OSError, sqlite3.Error, ValueError) as exc:
            gaps.append({"source": "sqlite", "error": type(exc).__name__})
            projects = []
        try:
            with (directory / "services.log").open("wb") as output:
                self.compose("logs", "--timestamps", "--no-color", stdout=output)
        except (OSError, subprocess.CalledProcessError) as exc:
            gaps.append({"source": "service_logs", "error": type(exc).__name__})
        config = load(self.evidence / "dispatch.json")
        prefix = self.manifest()["container_prefix"]
        try:
            listing = run(["docker", "ps", "-a", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
                          capture_output=True, text=True).stdout.splitlines()
        except (OSError, subprocess.CalledProcessError) as exc:
            gaps.append({"source": "worker_discovery", "error": type(exc).__name__})
            listing = []
        seen_workers = self.worker_projects() if final else set()
        for project, _status in projects:
            project_id(project)
            destination = directory / project
            destination.mkdir()
            container = prefix + project
            if container in listing:
                self.collect_worker(destination, container, config["workers"], gaps)
            elif project in seen_workers:
                gaps.append({"source": "worker_container", "project_id": project, "error": "missing"})
            if final:
                for suffix, route in (("graph.yaml", "export?format=yaml"), ("timeline.txt", "export?format=timeline")):
                    try:
                        (destination / suffix).write_bytes(self.api(f"/projects/{project}/{route}"))
                    except OSError as exc:
                        gaps.append({"source": suffix, "project_id": project, "error": type(exc).__name__})
        save(directory / "checkpoint.json", {"timestamp": now(), "final": final, "projects": projects, "gaps": gaps})
        print(directory)
        return directory, gaps

    def worker_projects(self):
        from review import read_rows

        return {row["project_id"] for _, row in read_rows(self.evidence / "dispatcher/events.jsonl")
                if isinstance(row, dict) and row.get("kind") == "worker_invocation" and "project_id" in row}

    def collect_worker(self, destination, container, workers, gaps):
        paths = {"workspace": "/home/kali/workspace", "prompts": "/tmp/cairn-prompts"}
        paths.update({worker["name"] + "-sessions": f"/tmp/cairn-pi/{worker['name']}/sessions" for worker in workers})
        for name, remote in paths.items():
            archive = destination / (name + ".tar")
            with archive.open("xb") as output:
                copy = subprocess.run(["docker", "cp", f"{container}:{remote}", "-"],
                                      stdout=output, stderr=subprocess.PIPE)
            if copy.returncode:
                detail = copy.stderr.decode(errors="replace").strip()
                if not archive.stat().st_size and ("Could not find the file" in detail or "no such file" in detail.lower()):
                    archive.unlink()
                    if name != "workspace":
                        continue
                gaps.append({"source": name, "container": container, "returncode": copy.returncode,
                             "detail": detail})

    def finish(self):
        self.require_unsealed()
        with closing(sqlite3.connect((self.directory / "state/cairn.db").as_uri() + "?mode=ro", uri=True)) as db:
            active = [row[0] for row in db.execute("SELECT id FROM projects WHERE status = 'active'")]
        if active:
            raise ValueError(f"stop active projects before finishing: {', '.join(active)}")
        prefix = self.manifest()["container_prefix"]
        deadline = time.monotonic() + 30
        while True:
            workers = run(["docker", "ps", "--filter", f"name={prefix}proj_", "--format", "{{.Names}}"],
                          capture_output=True, text=True).stdout.splitlines()
            if not workers:
                break
            if time.monotonic() >= deadline:
                raise ValueError(f"Cairn is still shutting down workers: {', '.join(workers)}")
            time.sleep(1)
        self.compose("stop", "--timeout", "30", "dispatcher")
        self.compose("stop", "--timeout", "30", "model-recorder")
        checkpoint, gaps = self.collect(final=True)
        self.compose("stop")
        from review import build_timeline

        gaps.extend(build_timeline(self.evidence))
        index = self.evidence / "index.json"
        items = [{"path": path.relative_to(self.evidence).as_posix(), "bytes": path.stat().st_size,
                  "sha256": checksum(path)} for path in sorted(self.evidence.rglob("*")) if path.is_file()]
        temporary = self.directory / "index.pending.json"
        temporary.unlink(missing_ok=True)
        save(temporary, {"run_id": self.run_id, "sealed_at": now(), "final_checkpoint": checkpoint.name,
                         "gaps": gaps, "files": items})
        temporary.replace(index)
        self.verify()

    def verify(self):
        index = load(self.evidence / "index.json")
        entries = {item["path"]: item for item in index["files"]}
        actual = {path.relative_to(self.evidence).as_posix(): path for path in self.evidence.rglob("*")
                  if path.is_file() and path != self.evidence / "index.json"}
        if entries.keys() != actual.keys() or len(entries) != len(index["files"]):
            raise ValueError("evidence file set differs from the index")
        for name, path in actual.items():
            entry = entries[name]
            if path.stat().st_size != entry["bytes"] or checksum(path) != entry["sha256"]:
                raise ValueError(f"evidence failed verification: {name}")
        print(f"Verified {len(entries)} files. Final checkpoint gaps: {len(index['gaps'])}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--port", type=int, default=8010)
    init.add_argument("--workers", type=int, default=2)
    init.add_argument("--model", default="deepseek-flash")
    init.add_argument("--model-url", default="https://api.deepseek.com")
    init.add_argument("--context-window", type=int, default=1_000_000)
    init.add_argument("--fixture", action="store_true")
    commands.add_parser("start")
    project = commands.add_parser("project")
    project.add_argument("spec", type=Path)
    stop = commands.add_parser("stop-project")
    stop.add_argument("project_id", type=project_id)
    submit = commands.add_parser("submission")
    submit.add_argument("project_id", type=project_id)
    submit.add_argument("receipt", type=Path)
    watch = commands.add_parser("watch")
    watch.add_argument("--interval", type=float, default=120)
    for name in ("snapshot", "finish", "verify"):
        commands.add_parser(name)
    args = parser.parse_args()
    try:
        competition = Competition(args.run_id)
        match args.command:
            case "init":
                competition.init(args)
            case "start":
                competition.start()
            case "project":
                competition.new_project(args.spec)
            case "stop-project":
                competition.stop_project(args.project_id)
            case "submission":
                competition.submission(args.project_id, args.receipt)
            case "snapshot":
                _, gaps = competition.collect()
                return bool(gaps)
            case "watch":
                if not math.isfinite(args.interval) or args.interval <= 0:
                    raise ValueError("interval must be positive")
                while True:
                    _, gaps = competition.collect()
                    if gaps:
                        print(f"Checkpoint has {len(gaps)} gaps; see checkpoint.json", file=sys.stderr)
                    time.sleep(args.interval)
            case "finish":
                competition.finish()
            case "verify":
                competition.verify()
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
