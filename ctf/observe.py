"""Record Cairn's existing task, API and Docker stream boundaries."""

from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import json
import logging
import os
from pathlib import Path
from pathlib import PurePosixPath
import signal
import sys
from threading import Lock
import time
from uuid import uuid4


EVIDENCE = Path("/evidence")
TASK = ContextVar("task", default={})
LOG = logging.getLogger(__name__)


class Journal:
    def __init__(self, root):
        self.root = root
        self.lock = Lock()

    def record(self, kind, **fields):
        row = dict(kind=kind, timestamp=datetime.now(timezone.utc).isoformat(),
                   monotonic_ns=time.monotonic_ns(), **fields)
        with self.lock:
            with (self.root / "events.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(row, ensure_ascii=True) + "\n")

    def emit(self, kind, **fields):
        try:
            self.record(kind, **fields)
        except OSError:
            LOG.exception("CTF capture failed kind=%s", kind)


class RecordedStream:
    def __init__(self, stream, directory, journal, invocation):
        self.stream = stream
        self.directory = directory
        self.journal = journal
        self.invocation = invocation
        self.failed = set()

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __iter__(self):
        for chunk in self.stream:
            stdout, stderr = chunk if isinstance(chunk, tuple) else (chunk, None)
            for name, payload in (("stdout", stdout), ("stderr", stderr)):
                if payload and name not in self.failed:
                    try:
                        with (self.directory / (name + ".bin")).open("ab") as output:
                            output.write(payload if isinstance(payload, bytes) else payload.encode())
                    except OSError:
                        self.failed.add(name)
                        self.journal.emit("capture_error", invocation=self.invocation, source=name)
                        LOG.exception("CTF capture failed invocation=%s source=%s", self.invocation, name)
            yield chunk


class ExecAPI:
    def __init__(self, api, directory, journal, invocation):
        self.api = api
        self.directory = directory
        self.journal = journal
        self.invocation = invocation

    def __getattr__(self, name):
        return getattr(self.api, name)

    def exec_create(self, *args, **kwargs):
        result = self.api.exec_create(*args, **kwargs)
        self.journal.emit("docker_exec_created", invocation=self.invocation, exec_id=result["Id"])
        return result

    def exec_start(self, *args, **kwargs):
        stream = self.api.exec_start(*args, **kwargs)
        return RecordedStream(stream, self.directory, self.journal, self.invocation)


def observe_task(task, phase):
    @wraps(task)
    def run(config, client, backend, project, *args):
        worker = args[-2]
        intent_id = args[-3].id if phase != "reason_execute" else None
        token = TASK.set(dict(project_id=project.project.id, intent_id=intent_id,
                              worker=worker.name, phase=phase))
        try:
            return task(config, client, backend, project, *args)
        finally:
            TASK.reset(token)

    return run


def attach(loop, scheduler, journal):
    for name, phase in (("run_bootstrap_task", "bootstrap"), ("run_explore_task", "explore_execute"),
                        ("run_reason_task", "reason_execute")):
        setattr(scheduler, name, observe_task(getattr(scheduler, name), phase))

    request = loop.client._request_json

    def record_request(method, path, json):
        started = time.monotonic_ns()
        result = request(method, path, json)
        journal.emit("cairn_api", method=method, path=path, request=json, response=result.data,
                     status=result.status_code, duration_ms=(time.monotonic_ns() - started) // 1_000_000)
        return result

    loop.client._request_json = record_request
    write_text = loop.container_manager.write_text_file

    def record_graph(container_name, path, content):
        result = write_text(container_name, path, content)
        graph = PurePosixPath(path)
        if graph.parent.parent == PurePosixPath("/tmp/cairn-prompts") and graph.name == "graph.yaml":
            artifact = Path("graphs") / graph.parent.name / graph.name
            try:
                output = journal.root / artifact
                output.parent.mkdir(parents=True)
                output.write_bytes(content.encode())
                journal.emit("graph_snapshot", container=container_name, worker_path=path,
                             artifact=f"dispatcher/{artifact.as_posix()}", **TASK.get())
            except OSError:
                journal.emit("capture_error", source="graph", container=container_name, worker_path=path)
        return result

    loop.container_manager.write_text_file = record_graph
    build = loop.container_manager.build_exec_process

    def record_process(container_name, env, command, **kwargs):
        process = build(container_name, env, command, **kwargs)
        invocation = uuid4().hex
        context = TASK.get().copy()
        # Pi places the rendered Cairn prompt last and uses --session for conclude.
        prompt = command[-1]
        pi_args = command[5:-2] if "PI_MODEL" in env else []
        session = None
        if "--session" in pi_args:
            session = pi_args[pi_args.index("--session") + 1]
            context["phase"] = context.get("phase", "unknown").removesuffix("_execute") + "_conclude"
        directory = journal.root / "workers" / invocation
        try:
            directory.mkdir(parents=True)
            (directory / "prompt.txt").write_bytes(prompt.encode())
        except OSError:
            journal.emit("capture_error", invocation=invocation, source="prompt")
        networks = process._container.attrs.get("NetworkSettings", {}).get("Networks", {})
        journal.emit("worker_invocation", invocation=invocation, container=container_name,
                     container_id=process._container.id,
                     addresses=[network.get("IPAddress") for network in networks.values() if network.get("IPAddress")],
                     resume_session=session, timeout_seconds=kwargs.get("timeout_seconds"), **context)
        process._api = ExecAPI(process._api, directory, journal, invocation)
        communicate = process.communicate

        def record_result(timeout):
            result = communicate(timeout)
            journal.emit("worker_result", invocation=invocation, returncode=result.returncode,
                         timed_out=result.timed_out, cancelled=result.cancelled,
                         cancel_reason=result.cancel_reason, stream_error=bool(process._read_error))
            return result

        process.communicate = record_result
        return process

    loop.container_manager.build_exec_process = record_process


def main():
    from cairn.dispatcher.logging import configure_logging
    from cairn.dispatcher.scheduler import loop as scheduler

    configure_logging("DEBUG")
    ready = EVIDENCE / "dispatcher-ready"
    ready.unlink(missing_ok=True)
    loop = scheduler.DispatcherLoop(Path("/config/dispatch.json"))
    loop.container_manager._PREFIX = os.environ["CTF_CONTAINER_PREFIX"]
    attach(loop, scheduler, Journal(EVIDENCE))

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        loop.run_startup_healthchecks()
        ready.touch()
        loop.run()
    except KeyboardInterrupt:
        return 130
    finally:
        ready.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
