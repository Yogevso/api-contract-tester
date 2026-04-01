"""Diff engine — compare API responses between two environments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from api_contract_tester.executor import ResponseData


@dataclass
class FieldDiff:
    """A single field-level difference between two responses."""
    path: str
    left: Any
    right: Any


@dataclass
class ResponseDiff:
    """Full diff result comparing two responses for the same test."""
    test_name: str
    status_match: bool
    left_status: int
    right_status: int
    body_diffs: list[FieldDiff] = field(default_factory=list)
    header_diffs: list[FieldDiff] = field(default_factory=list)
    left_error: str | None = None
    right_error: str | None = None

    @property
    def identical(self) -> bool:
        return (
            self.status_match
            and not self.body_diffs
            and not self.header_diffs
            and not self.left_error
            and not self.right_error
        )


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict/list into dot-path keys."""
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


def compare_responses(
    test_name: str,
    left: ResponseData,
    right: ResponseData,
    ignore_headers: set[str] | None = None,
) -> ResponseDiff:
    """Compare two responses and return a structured diff."""
    ignore_headers = ignore_headers or set()

    diff = ResponseDiff(
        test_name=test_name,
        status_match=left.status_code == right.status_code,
        left_status=left.status_code,
        right_status=right.status_code,
        left_error=left.error,
        right_error=right.error,
    )

    # Compare body fields
    left_flat = _flatten(left.body) if isinstance(left.body, (dict, list)) else {}
    right_flat = _flatten(right.body) if isinstance(right.body, (dict, list)) else {}
    all_keys = sorted(set(left_flat) | set(right_flat))

    for key in all_keys:
        left_val = left_flat.get(key, "<missing>")
        right_val = right_flat.get(key, "<missing>")
        if left_val != right_val:
            diff.body_diffs.append(FieldDiff(path=key, left=left_val, right=right_val))

    # Compare headers (case-insensitive, skip ignored ones)
    left_hdrs = {k.lower(): v for k, v in left.headers.items()}
    right_hdrs = {k.lower(): v for k, v in right.headers.items()}
    compare_header_keys = {"content-type", "cache-control", "x-request-id"}
    compare_header_keys -= {h.lower() for h in ignore_headers}

    for key in sorted(compare_header_keys & (set(left_hdrs) | set(right_hdrs))):
        left_val = left_hdrs.get(key, "<missing>")
        right_val = right_hdrs.get(key, "<missing>")
        if left_val != right_val:
            diff.header_diffs.append(FieldDiff(path=key, left=left_val, right=right_val))

    return diff
