"""Validate a Cairn experiment run directory against protocol version 1.0.

The validator deliberately uses only the Python standard library so the research
protocol does not change Cairn's frozen runtime dependencies.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any


PROTOCOL_VERSION = "1.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = REPOSITORY_ROOT / "schemas" / "run-v1"

SCHEMA_FILES = {
    "manifest": "run-manifest.schema.json",
    "event": "run-event.schema.json",
    "result": "run-result.schema.json",
    "metrics": "run-metrics.schema.json",
    "artifact": "artifact-record.schema.json",
    "graph": "graph-snapshot.schema.json",
}

REQUIRED_RUN_FILES = {
    "manifest": Path("manifest.json"),
    "events": Path("events.jsonl"),
    "result": Path("result.json"),
    "metrics": Path("metrics.json"),
    "graph": Path("graph_snapshot.json"),
    "artifacts": Path("artifacts/index.jsonl"),
}

SECRET_KEY_PATTERN = re.compile(
    r"(?:^|_)(?:api_key|authorization|password|private_key|refresh_token|access_token|secret|secret_value)$",
    re.IGNORECASE,
)


class ProtocolValidationError(ValueError):
    """Raised when one or more protocol violations are found."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _resolve_ref(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"unsupported schema reference: {reference}")
    current: Any = root_schema
    for part in reference[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError(f"schema reference does not resolve to an object: {reference}")
    return current


def _validate_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> list[str]:
    errors: list[str] = []

    if "$ref" in schema:
        return _validate_schema(value, _resolve_ref(root_schema, schema["$ref"]), root_schema=root_schema, path=path)

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = [expected_type] if isinstance(expected_type, str) else expected_type
        if not any(_json_type_matches(value, item) for item in expected_types):
            errors.append(f"{path}: expected type {expected_types!r}")
            return errors

    for branch in schema.get("allOf", []):
        errors.extend(_validate_schema(value, branch, root_schema=root_schema, path=path))

    if "anyOf" in schema:
        branch_errors = [
            _validate_schema(value, branch, root_schema=root_schema, path=path)
            for branch in schema["anyOf"]
        ]
        if all(item for item in branch_errors):
            errors.append(f"{path}: does not match any allowed schema")

    if "oneOf" in schema:
        matches = sum(
            not _validate_schema(value, branch, root_schema=root_schema, path=path)
            for branch in schema["oneOf"]
        )
        if matches != 1:
            errors.append(f"{path}: must match exactly one allowed schema")

    if "if" in schema:
        condition_errors = _validate_schema(value, schema["if"], root_schema=root_schema, path=path)
        selected = schema.get("else") if condition_errors else schema.get("then")
        if selected is not None:
            errors.extend(_validate_schema(value, selected, root_schema=root_schema, path=path))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")

        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                errors.extend(
                    _validate_schema(child, properties[key], root_schema=root_schema, path=f"{path}.{key}")
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unknown property {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(
                    _validate_schema(
                        child,
                        schema["additionalProperties"],
                        root_schema=root_schema,
                        path=f"{path}.{key}",
                    )
                )

        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: must contain at least {schema['minProperties']} properties")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: must contain at least {schema['minItems']} items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_schema(item, item_schema, root_schema=root_schema, path=f"{path}[{index}]")
                )

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            errors.append(f"{path}: does not match required pattern")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                errors.append(f"{path}: must be an RFC 3339 timestamp with an offset")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be >= {schema['minimum']}")

    return errors


def _load_json(path: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: file is missing")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: cannot read JSON: {exc}")
    return None


def _load_jsonl(path: Path, errors: list[str]) -> list[Any]:
    records: list[Any] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        errors.append(f"{path}: file is missing")
        return records
    except (OSError, UnicodeError) as exc:
        errors.append(f"{path}: cannot read JSONL: {exc}")
        return records

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"{path}:{line_number}: blank lines are not allowed")
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
    return records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_secret_keys(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if SECRET_KEY_PATTERN.search(key):
                errors.append(f"{child_path}: secret-bearing keys are forbidden")
            errors.extend(_find_secret_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_find_secret_keys(child, f"{path}[{index}]"))
    return errors


def _safe_artifact_path(run_dir: Path, relative_path: str) -> Path | None:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != "artifacts":
        return None
    candidate = run_dir.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(run_dir.resolve())
    except (OSError, ValueError):
        return None
    return candidate


def _validate_cross_file(
    run_dir: Path,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    result: dict[str, Any],
    metrics: dict[str, Any],
    artifacts: list[dict[str, Any]],
    graph: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    run_id = manifest["run_id"]
    task_id = manifest["task"]["task_id"]
    evaluator_version = manifest["evaluator_version"]

    for label, value in [("result", result), ("metrics", metrics), ("graph_snapshot", graph)]:
        if value["run_id"] != run_id:
            errors.append(f"{label}.run_id: must equal manifest run_id {run_id!r}")

    if result["evaluator_version"] != evaluator_version:
        errors.append("result.evaluator_version: must equal manifest evaluator_version")
    if metrics["derived_from"]["evaluator_version"] != evaluator_version:
        errors.append("metrics.derived_from.evaluator_version: must equal manifest evaluator_version")
    if manifest["workers"]["count"] != len(manifest["workers"]["configuration"]):
        errors.append("manifest.workers.count: must equal the number of worker configurations")

    event_ids: set[str] = set()
    artifact_ids = {item["artifact_id"] for item in artifacts}
    previous_monotonic = -1
    for index, event in enumerate(events, start=1):
        prefix = f"events.jsonl:{index}"
        if event["run_id"] != run_id:
            errors.append(f"{prefix}.run_id: must equal manifest run_id {run_id!r}")
        if event["task_id"] != task_id:
            errors.append(f"{prefix}.task_id: must equal manifest task_id {task_id!r}")
        if event["sequence"] != index:
            errors.append(f"{prefix}.sequence: expected contiguous sequence value {index}")
        if event["event_id"] in event_ids:
            errors.append(f"{prefix}.event_id: duplicate event ID {event['event_id']!r}")
        parent = event["parent_event_id"]
        if parent is not None and parent not in event_ids:
            errors.append(f"{prefix}.parent_event_id: must reference an earlier event")
        unknown_artifacts = set(event["related_artifact_ids"]) - artifact_ids
        if unknown_artifacts:
            errors.append(f"{prefix}.related_artifact_ids: unknown IDs {sorted(unknown_artifacts)!r}")
        if event["monotonic_ms"] < previous_monotonic:
            errors.append(f"{prefix}.monotonic_ms: must not decrease")
        usage = event["token_usage"]
        if usage is not None and usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
            errors.append(f"{prefix}.token_usage.total_tokens: must equal input_tokens + output_tokens")
        previous_monotonic = event["monotonic_ms"]
        event_ids.add(event["event_id"])

    if not events:
        errors.append("events.jsonl: must contain at least one event")
    else:
        if events[0]["event_type"] != "run_started":
            errors.append("events.jsonl: first event must be run_started")
        elif events[0]["payload"]["system_version"] != manifest["system"]["system_version"]:
            errors.append("events.jsonl: run_started system_version must match manifest")
        if manifest["run_state"] == "finished" and events[-1]["event_type"] != "run_finished":
            errors.append("events.jsonl: a finished run must end with run_finished")

    if manifest["run_state"] == "interrupted" and result["termination_reason"] != "run_interrupted":
        errors.append("result.termination_reason: interrupted runs must use run_interrupted")

    if events and events[-1]["event_type"] == "run_finished":
        event_reason = events[-1]["payload"]["termination_reason"]
        if event_reason != result["termination_reason"]:
            errors.append("result.termination_reason: must match the run_finished event")

    accepted_event_submission_ids = {
        event["payload"]["submission_id"]
        for event in events
        if event["event_type"] == "flag_accepted"
    }
    if result["status"] == "SOLVED":
        submission_id = result["accepted_submission"]["submission_id"]
        if submission_id not in accepted_event_submission_ids:
            errors.append("result.accepted_submission: no matching flag_accepted event")
    elif accepted_event_submission_ids:
        errors.append("result.status: flag_accepted events require SOLVED")

    events_path = run_dir / REQUIRED_RUN_FILES["events"]
    if metrics["derived_from"]["events_sha256"] != _sha256(events_path):
        errors.append("metrics.derived_from.events_sha256: does not match events.jsonl")

    artifact_event_ids = {
        event["payload"]["artifact_id"]
        for event in events
        if event["event_type"] == "artifact_created"
    }
    seen_artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts, start=1):
        prefix = f"artifacts/index.jsonl:{index}"
        if artifact["run_id"] != run_id:
            errors.append(f"{prefix}.run_id: must equal manifest run_id {run_id!r}")
        if artifact["artifact_id"] in seen_artifact_ids:
            errors.append(f"{prefix}.artifact_id: duplicate artifact ID {artifact['artifact_id']!r}")
        seen_artifact_ids.add(artifact["artifact_id"])
        path = _safe_artifact_path(run_dir, artifact["relative_path"])
        if path is None:
            errors.append(f"{prefix}.relative_path: must be a safe path below artifacts/")
            continue
        if not path.is_file():
            errors.append(f"{prefix}.relative_path: referenced file is missing")
            continue
        if path.stat().st_size != artifact["size_bytes"]:
            errors.append(f"{prefix}.size_bytes: does not match the artifact file")
        if _sha256(path) != artifact["sha256"]:
            errors.append(f"{prefix}.sha256: does not match the artifact file")
        if artifact["artifact_id"] not in artifact_event_ids:
            errors.append(f"{prefix}.artifact_id: no matching artifact_created event")
        if artifact["producer_event_id"] not in event_ids:
            errors.append(f"{prefix}.producer_event_id: unknown event ID")
        redaction = artifact["redaction"]
        if redaction["applied"] != (redaction["method"] is not None):
            errors.append(f"{prefix}.redaction: method must be set exactly when redaction is applied")

    if graph["last_event_sequence"] > len(events):
        errors.append("graph_snapshot.last_event_sequence: exceeds the event stream")

    fact_ids = [fact["id"] for fact in graph["facts"]]
    intent_ids = [intent["id"] for intent in graph["intents"]]
    hint_ids = [hint["id"] for hint in graph["hints"]]
    if len(fact_ids) != len(set(fact_ids)):
        errors.append("graph_snapshot.facts: fact IDs must be unique")
    if len(intent_ids) != len(set(intent_ids)):
        errors.append("graph_snapshot.intents: intent IDs must be unique")
    if len(hint_ids) != len(set(hint_ids)):
        errors.append("graph_snapshot.hints: hint IDs must be unique")
    known_facts = set(fact_ids)
    for index, intent in enumerate(graph["intents"]):
        unknown_sources = set(intent["from"]) - known_facts
        if unknown_sources:
            errors.append(
                f"graph_snapshot.intents[{index}].from: unknown fact IDs {sorted(unknown_sources)!r}"
            )
        if intent["to"] is not None and intent["to"] not in known_facts:
            errors.append(f"graph_snapshot.intents[{index}].to: unknown fact ID {intent['to']!r}")

    event_counts = {
        "llm_calls": sum(event["event_type"] == "llm_call_completed" for event in events),
        "tool_calls": sum(event["event_type"] == "tool_call_completed" for event in events),
        "runtime_failures": sum(event["event_type"] == "runtime_error" for event in events),
        "facts_created": sum(event["event_type"] == "fact_created" for event in events),
        "intents_created": sum(event["event_type"] == "intent_created" for event in events),
        "intents_completed": sum(event["event_type"] == "intent_completed" for event in events),
        "intents_abandoned": sum(event["event_type"] == "intent_abandoned" for event in events),
        "artifacts_created": sum(event["event_type"] == "artifact_created" for event in events),
    }
    for metric, expected in event_counts.items():
        if metrics["values"][metric] != expected:
            errors.append(f"metrics.values.{metric}: expected {expected} from events.jsonl")

    completed_llm_calls = [event for event in events if event["event_type"] == "llm_call_completed"]
    expected_tokens = (
        None
        if any(event["token_usage"] is None for event in completed_llm_calls)
        else sum(event["token_usage"]["total_tokens"] for event in completed_llm_calls)
    )
    expected_cost = (
        None
        if any(event["cost_usd"] is None for event in completed_llm_calls)
        else sum(event["cost_usd"] for event in completed_llm_calls)
    )
    if metrics["values"]["tokens_total"] != expected_tokens:
        errors.append(f"metrics.values.tokens_total: expected {expected_tokens!r} from completed LLM calls")
    if metrics["values"]["cost_total_usd"] != expected_cost:
        errors.append(f"metrics.values.cost_total_usd: expected {expected_cost!r} from completed LLM calls")

    accepted_events = [event for event in events if event["event_type"] == "flag_accepted"]
    expected_time_to_flag = accepted_events[0]["monotonic_ms"] if accepted_events else None
    if metrics["values"]["time_to_flag_ms"] != expected_time_to_flag:
        errors.append(f"metrics.values.time_to_flag_ms: expected {expected_time_to_flag!r} from events.jsonl")

    if accepted_events:
        calls_to_flag = [
            event
            for event in completed_llm_calls
            if event["monotonic_ms"] <= accepted_events[0]["monotonic_ms"]
        ]
        expected_tokens_to_flag = (
            None
            if any(event["token_usage"] is None for event in calls_to_flag)
            else sum(event["token_usage"]["total_tokens"] for event in calls_to_flag)
        )
    else:
        expected_tokens_to_flag = None
    if metrics["values"]["tokens_to_flag"] != expected_tokens_to_flag:
        errors.append(
            f"metrics.values.tokens_to_flag: expected {expected_tokens_to_flag!r} from events.jsonl"
        )

    errors.extend(_find_secret_keys(manifest, "manifest"))
    errors.extend(_find_secret_keys(events, "events"))
    errors.extend(_find_secret_keys(result, "result"))
    errors.extend(_find_secret_keys(metrics, "metrics"))
    errors.extend(_find_secret_keys(artifacts, "artifacts"))
    errors.extend(_find_secret_keys(graph, "graph_snapshot"))
    return errors


def validate_run(run_dir: str | Path, *, schema_root: str | Path | None = None) -> None:
    """Validate one run directory or raise :class:`ProtocolValidationError`."""

    directory = Path(run_dir)
    schemas_path = Path(schema_root) if schema_root is not None else SCHEMA_ROOT
    errors: list[str] = []
    if not directory.is_dir():
        raise ProtocolValidationError([f"{directory}: run directory does not exist"])

    schemas: dict[str, dict[str, Any]] = {}
    for name, filename in SCHEMA_FILES.items():
        loaded = _load_json(schemas_path / filename, errors)
        if isinstance(loaded, dict):
            schemas[name] = loaded

    loaded_files = {
        "manifest": _load_json(directory / REQUIRED_RUN_FILES["manifest"], errors),
        "result": _load_json(directory / REQUIRED_RUN_FILES["result"], errors),
        "metrics": _load_json(directory / REQUIRED_RUN_FILES["metrics"], errors),
        "graph": _load_json(directory / REQUIRED_RUN_FILES["graph"], errors),
    }
    events = _load_jsonl(directory / REQUIRED_RUN_FILES["events"], errors)
    artifacts = _load_jsonl(directory / REQUIRED_RUN_FILES["artifacts"], errors)

    if errors:
        raise ProtocolValidationError(errors)

    for name, value in loaded_files.items():
        assert value is not None
        errors.extend(_validate_schema(value, schemas[name], root_schema=schemas[name], path=name))
    for index, event in enumerate(events, start=1):
        errors.extend(
            _validate_schema(event, schemas["event"], root_schema=schemas["event"], path=f"events[{index}]")
        )
    for index, artifact in enumerate(artifacts, start=1):
        errors.extend(
            _validate_schema(
                artifact,
                schemas["artifact"],
                root_schema=schemas["artifact"],
                path=f"artifacts[{index}]",
            )
        )

    if errors:
        raise ProtocolValidationError(errors)

    manifest = loaded_files["manifest"]
    result = loaded_files["result"]
    metrics = loaded_files["metrics"]
    graph = loaded_files["graph"]
    assert isinstance(manifest, dict)
    assert isinstance(result, dict)
    assert isinstance(metrics, dict)
    assert isinstance(graph, dict)
    cross_file_errors = _validate_cross_file(directory, manifest, events, result, metrics, artifacts, graph)
    if cross_file_errors:
        raise ProtocolValidationError(cross_file_errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Cairn experiment run directory")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--schema-root", type=Path, default=SCHEMA_ROOT)
    args = parser.parse_args(argv)

    try:
        validate_run(args.run_dir, schema_root=args.schema_root)
    except ProtocolValidationError as exc:
        for error in exc.errors:
            print(f"ERROR: {error}")
        return 1
    print(f"valid Cairn run protocol {PROTOCOL_VERSION}: {args.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
