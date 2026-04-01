"""Snapshot testing — save and compare API responses over time."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api_contract_tester.executor import ResponseData

SNAPSHOT_DIR = ".snapshots"


@dataclass
class SnapshotMismatch:
    """A field-level mismatch between snapshot and live response."""
    path: str
    expected: Any
    actual: Any


@dataclass
class SnapshotResult:
    """Result of comparing a live response against a stored snapshot."""
    test_name: str
    suite_name: str
    matched: bool
    mismatches: list[SnapshotMismatch] = field(default_factory=list)
    snapshot_missing: bool = False


def _snapshot_path(base_dir: Path, suite_name: str, test_name: str) -> Path:
    """Build the snapshot file path for a given suite/test."""
    safe_suite = suite_name.replace(" ", "_").replace("/", "_")
    safe_test = test_name.replace(" ", "_").replace("/", "_")
    return base_dir / SNAPSHOT_DIR / safe_suite / f"{safe_test}.json"


def save_snapshot(
    base_dir: Path,
    suite_name: str,
    test_name: str,
    response: ResponseData,
) -> Path:
    """Persist a response as a snapshot JSON file. Returns the path written."""
    path = _snapshot_path(base_dir, suite_name, test_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": response.body,
    }
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def load_snapshot(base_dir: Path, suite_name: str, test_name: str) -> dict[str, Any] | None:
    """Load a previously saved snapshot. Returns None if not found."""
    path = _snapshot_path(base_dir, suite_name, test_name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested data into dot-path keys."""
    result: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            result.update(_flatten(v, full_key))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            full_key = f"{prefix}.{i}" if prefix else str(i)
            result.update(_flatten(v, full_key))
    else:
        result[prefix] = data
    return result


def compare_snapshot(
    suite_name: str,
    test_name: str,
    snapshot: dict[str, Any],
    response: ResponseData,
) -> SnapshotResult:
    """Compare a live response against a stored snapshot."""
    mismatches: list[SnapshotMismatch] = []

    # Status code
    if snapshot["status_code"] != response.status_code:
        mismatches.append(SnapshotMismatch(
            path="status_code",
            expected=snapshot["status_code"],
            actual=response.status_code,
        ))

    # Body
    snap_body = snapshot.get("body")
    snap_flat = _flatten(snap_body) if isinstance(snap_body, (dict, list)) else {}
    resp_flat = _flatten(response.body) if isinstance(response.body, (dict, list)) else {}
    all_keys = sorted(set(snap_flat) | set(resp_flat))

    for key in all_keys:
        snap_val = snap_flat.get(key, "<missing>")
        resp_val = resp_flat.get(key, "<missing>")
        if snap_val != resp_val:
            mismatches.append(SnapshotMismatch(
                path=f"body.{key}", expected=snap_val, actual=resp_val
            ))

    return SnapshotResult(
        test_name=test_name,
        suite_name=suite_name,
        matched=len(mismatches) == 0,
        mismatches=mismatches,
    )
