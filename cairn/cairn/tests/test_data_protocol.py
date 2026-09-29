from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from experiments.protocol.validate import ProtocolValidationError, validate_run


EXAMPLE_RUN = REPOSITORY_ROOT / "examples" / "run-v1" / "complete"


def copy_example(tmp_path: Path) -> Path:
    destination = tmp_path / "run"
    shutil.copytree(EXAMPLE_RUN, destination)
    return destination


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def test_complete_protocol_example_is_valid() -> None:
    validate_run(EXAMPLE_RUN)


def test_non_contiguous_event_sequence_is_rejected(tmp_path: Path) -> None:
    run_dir = copy_example(tmp_path)
    events_path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    events[2]["sequence"] = 9
    events_path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    with pytest.raises(ProtocolValidationError, match="expected contiguous sequence value 3"):
        validate_run(run_dir)


def test_inconsistent_result_state_is_rejected(tmp_path: Path) -> None:
    run_dir = copy_example(tmp_path)
    result_path = run_dir / "result.json"
    result = read_json(result_path)
    result["status"] = "RUNTIME_INVALID"
    write_json(result_path, result)

    with pytest.raises(ProtocolValidationError, match="must equal 'INVALID'"):
        validate_run(run_dir)


def test_artifact_path_traversal_is_rejected(tmp_path: Path) -> None:
    run_dir = copy_example(tmp_path)
    index_path = run_dir / "artifacts" / "index.jsonl"
    artifact = json.loads(index_path.read_text(encoding="utf-8"))
    artifact["relative_path"] = "artifacts/../manifest.json"
    index_path.write_text(json.dumps(artifact) + "\n", encoding="utf-8")

    with pytest.raises(ProtocolValidationError):
        validate_run(run_dir)


def test_secret_bearing_manifest_key_is_rejected(tmp_path: Path) -> None:
    run_dir = copy_example(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["model"]["parameters"]["api_key"] = "do-not-store-this"
    write_json(manifest_path, manifest)

    with pytest.raises(ProtocolValidationError, match="secret-bearing keys are forbidden"):
        validate_run(run_dir)


def test_event_specific_payload_is_required(tmp_path: Path) -> None:
    run_dir = copy_example(tmp_path)
    events_path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    events[1]["payload"] = {}
    events_path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    with pytest.raises(ProtocolValidationError, match="missing required property 'worker_type'"):
        validate_run(run_dir)


def test_metric_count_must_be_reproducible_from_events(tmp_path: Path) -> None:
    run_dir = copy_example(tmp_path)
    metrics_path = run_dir / "metrics.json"
    metrics = read_json(metrics_path)
    metrics["values"]["facts_created"] = 2
    write_json(metrics_path, metrics)

    with pytest.raises(ProtocolValidationError, match="expected 1 from events.jsonl"):
        validate_run(run_dir)
