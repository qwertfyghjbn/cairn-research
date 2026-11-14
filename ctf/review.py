"""Merge the run evidence into a timeline with links back to original records."""

import json
from datetime import datetime
from pathlib import Path


def read_rows(path):
    if not path.exists():
        return
    with path.open("rb") as stream:
        for number, line in enumerate(stream, 1):
            try:
                yield number, json.loads(line)
            except (ValueError, UnicodeError):
                yield number, None


def model_usage(path):
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        first = stream.read(1)
        stream.seek(0)
        if first == b"{":
            try:
                row = json.load(stream)
                return row.get("usage") if isinstance(row, dict) else None
            except (ValueError, UnicodeError):
                return None
        usage = None
        for line in stream:
            if line.startswith(b"data:"):
                try:
                    data = json.loads(line[5:])
                except (ValueError, UnicodeError):
                    continue
                if isinstance(data, dict) and isinstance(data.get("usage"), dict):
                    usage = data["usage"]
        return usage


def build_timeline(evidence: Path):
    rows, gaps, invocations, results, calls, response_ends = [], [], {}, {}, {}, set()
    for source in ("dispatcher/events.jsonl", "model/events.jsonl"):
        for line, row in read_rows(evidence / source):
            if not isinstance(row, dict):
                gaps.append({"source": source, "line": line, "error": "invalid_jsonl"})
                continue
            row["source"] = {"path": source, "line": line}
            kind = row["kind"]
            if kind == "worker_invocation":
                invocations[row["invocation"]] = row
                prefix = f"dispatcher/workers/{row['invocation']}"
                row["artifacts"] = [f"{prefix}/{name}" for name in ("prompt.txt", "stdout.bin", "stderr.bin")
                                    if (evidence / prefix / name).is_file()]
                stdout = evidence / prefix / "stdout.bin"
                for _, event in read_rows(stdout):
                    if isinstance(event, dict) and event.get("type") == "session" and event.get("id"):
                        row["session_id"] = event["id"]
                        break
                if "session_id" not in row and row.get("resume_session"):
                    row["session_id"] = row["resume_session"]
            elif kind == "worker_result":
                results[row["invocation"]] = row
                if row.get("stream_error"):
                    gaps.append({"source": source, "line": line, "error": "worker_stream_error"})
            elif kind == "model_request":
                calls[row["call_id"]] = row
                row["artifacts"] = [f"model/{row['call_id']}/{name}" for name in ("request.json", "response.bin")
                                    if (evidence / "model" / row["call_id"] / name).is_file()]
            elif kind == "model_response_end":
                response_ends.add(row["call_id"])
                usage = model_usage(evidence / "model" / row["call_id"] / "response.bin")
                if usage is not None:
                    row["usage"] = usage
            elif kind == "cairn_api":
                row["project_id"] = row["path"].split("/")[2]
                row.pop("request", None)
                row.pop("response", None)
            if kind == "capture_error" or row.get("captured") is False or row.get("complete") is False:
                gaps.append({"source": source, "line": line, "error": kind})
            rows.append(row)

    for invocation, row in invocations.items():
        if invocation not in results:
            gaps.append({"source": "dispatcher/events.jsonl", "invocation": invocation,
                         "error": "worker_result_missing"})
    for call, row in calls.items():
        if call not in response_ends:
            gaps.append({"source": "model/events.jsonl", "call_id": call, "error": "model_response_end_missing"})
        matches = [invocation for invocation, task in invocations.items()
                   if task.get("worker") == row["worker"] and row["client_ip"] in task.get("addresses", [])
                   and task["timestamp"] <= row["timestamp"]
                   and (invocation not in results or row["timestamp"] <= results[invocation]["timestamp"])]
        if len(matches) == 1:
            row["invocation"] = matches[0]
            row["project_id"] = invocations[matches[0]]["project_id"]
            row["attribution"] = "worker_container_ip_and_time"
        else:
            row["attribution"] = "ambiguous" if matches else "unattributed"

    for row in rows:
        if row["kind"] == "worker_result" or row["kind"] == "docker_exec_created":
            task = invocations.get(row["invocation"], {})
            row.update({key: task[key] for key in ("project_id", "intent_id", "worker", "phase", "session_id")
                        if key in task})
        elif row["kind"] in ("model_response_headers", "model_response_end"):
            call = calls.get(row["call_id"], {})
            row.update({key: call[key] for key in ("project_id", "worker", "invocation") if key in call})

    for path in sorted((evidence / "submissions").glob("*.json")):
        receipt = json.loads(path.read_bytes())
        rows.append({"kind": "submission_receipt",
                     "timestamp": receipt["receipt"].get("submitted_at") or receipt["recorded_at"],
                     "project_id": receipt["project_id"], "accepted": receipt["receipt"]["accepted"],
                     "source": {"path": path.relative_to(evidence).as_posix()}})

    timeline = evidence / "timeline.jsonl"
    temporary = timeline.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in sorted(rows, key=lambda item: datetime.fromisoformat(item["timestamp"])):
            stream.write(json.dumps(row, ensure_ascii=True) + "\n")
    temporary.replace(timeline)
    return gaps
