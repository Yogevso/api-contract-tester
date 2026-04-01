"""Tests for the diff engine."""

from __future__ import annotations

from api_contract_tester.diff import FieldDiff, ResponseDiff, compare_responses, _flatten
from api_contract_tester.executor import ResponseData


class TestFlatten:
    def test_flat_dict(self):
        assert _flatten({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested_dict(self):
        result = _flatten({"user": {"name": "Alice", "age": 30}})
        assert result == {"user.name": "Alice", "user.age": 30}

    def test_list(self):
        result = _flatten({"items": [10, 20]})
        assert result == {"items.0": 10, "items.1": 20}

    def test_nested_list_of_dicts(self):
        result = _flatten({"users": [{"name": "A"}, {"name": "B"}]})
        assert result == {"users.0.name": "A", "users.1.name": "B"}

    def test_scalar(self):
        assert _flatten(42) == {"": 42}

    def test_empty_dict(self):
        assert _flatten({}) == {}


class TestCompareResponses:
    def test_identical(self):
        left = ResponseData(status_code=200, headers={}, body={"id": 1}, elapsed_ms=10)
        right = ResponseData(status_code=200, headers={}, body={"id": 1}, elapsed_ms=15)
        diff = compare_responses("test", left, right)
        assert diff.identical
        assert diff.status_match
        assert diff.body_diffs == []

    def test_status_differs(self):
        left = ResponseData(status_code=200, headers={}, body={}, elapsed_ms=10)
        right = ResponseData(status_code=500, headers={}, body={}, elapsed_ms=10)
        diff = compare_responses("test", left, right)
        assert not diff.identical
        assert not diff.status_match
        assert diff.left_status == 200
        assert diff.right_status == 500

    def test_body_field_differs(self):
        left = ResponseData(status_code=200, headers={}, body={"name": "John"}, elapsed_ms=10)
        right = ResponseData(status_code=200, headers={}, body={"name": "John Doe"}, elapsed_ms=10)
        diff = compare_responses("test", left, right)
        assert not diff.identical
        assert len(diff.body_diffs) == 1
        assert diff.body_diffs[0].path == "name"
        assert diff.body_diffs[0].left == "John"
        assert diff.body_diffs[0].right == "John Doe"

    def test_body_field_missing_on_right(self):
        left = ResponseData(status_code=200, headers={}, body={"a": 1, "b": 2}, elapsed_ms=10)
        right = ResponseData(status_code=200, headers={}, body={"a": 1}, elapsed_ms=10)
        diff = compare_responses("test", left, right)
        assert not diff.identical
        assert any(d.path == "b" for d in diff.body_diffs)

    def test_nested_body_diff(self):
        left = ResponseData(
            status_code=200, headers={},
            body={"user": {"role": "admin"}}, elapsed_ms=10,
        )
        right = ResponseData(
            status_code=200, headers={},
            body={"user": {"role": "viewer"}}, elapsed_ms=10,
        )
        diff = compare_responses("test", left, right)
        assert not diff.identical
        assert diff.body_diffs[0].path == "user.role"

    def test_error_on_left(self):
        left = ResponseData(status_code=0, headers={}, body=None, elapsed_ms=0, error="timeout")
        right = ResponseData(status_code=200, headers={}, body={"ok": True}, elapsed_ms=10)
        diff = compare_responses("test", left, right)
        assert not diff.identical
        assert diff.left_error == "timeout"

    def test_header_diff(self):
        left = ResponseData(
            status_code=200,
            headers={"content-type": "application/json"},
            body={}, elapsed_ms=10,
        )
        right = ResponseData(
            status_code=200,
            headers={"content-type": "text/plain"},
            body={}, elapsed_ms=10,
        )
        diff = compare_responses("test", left, right)
        assert not diff.identical
        assert any(d.path == "content-type" for d in diff.header_diffs)

    def test_non_json_bodies(self):
        left = ResponseData(status_code=200, headers={}, body="hello", elapsed_ms=10)
        right = ResponseData(status_code=200, headers={}, body="hello", elapsed_ms=10)
        diff = compare_responses("test", left, right)
        assert diff.identical
