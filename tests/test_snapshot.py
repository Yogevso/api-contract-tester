"""Tests for the snapshot module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api_contract_tester.executor import ResponseData
from api_contract_tester.snapshot import (
    SnapshotResult,
    compare_snapshot,
    load_snapshot,
    save_snapshot,
)


class TestSaveAndLoadSnapshot:
    def test_round_trip(self, tmp_path):
        response = ResponseData(
            status_code=200,
            headers={"content-type": "application/json"},
            body={"id": 1, "name": "test"},
            elapsed_ms=50,
        )
        save_snapshot(tmp_path, "my-suite", "test one", response)
        loaded = load_snapshot(tmp_path, "my-suite", "test one")
        assert loaded is not None
        assert loaded["status_code"] == 200
        assert loaded["body"]["id"] == 1
        assert loaded["body"]["name"] == "test"

    def test_load_missing(self, tmp_path):
        result = load_snapshot(tmp_path, "nonexistent", "nothing")
        assert result is None

    def test_creates_nested_dirs(self, tmp_path):
        response = ResponseData(
            status_code=200, headers={}, body={"ok": True}, elapsed_ms=10,
        )
        path = save_snapshot(tmp_path, "deep/suite", "a test", response)
        assert path.exists()

    def test_overwrites_existing(self, tmp_path):
        resp1 = ResponseData(status_code=200, headers={}, body={"v": 1}, elapsed_ms=10)
        resp2 = ResponseData(status_code=200, headers={}, body={"v": 2}, elapsed_ms=10)
        save_snapshot(tmp_path, "s", "t", resp1)
        save_snapshot(tmp_path, "s", "t", resp2)
        loaded = load_snapshot(tmp_path, "s", "t")
        assert loaded["body"]["v"] == 2


class TestCompareSnapshot:
    def test_identical(self):
        snapshot = {"status_code": 200, "headers": {}, "body": {"id": 1}}
        response = ResponseData(status_code=200, headers={}, body={"id": 1}, elapsed_ms=10)
        result = compare_snapshot("suite", "test", snapshot, response)
        assert result.matched
        assert result.mismatches == []

    def test_status_mismatch(self):
        snapshot = {"status_code": 200, "headers": {}, "body": {}}
        response = ResponseData(status_code=500, headers={}, body={}, elapsed_ms=10)
        result = compare_snapshot("suite", "test", snapshot, response)
        assert not result.matched
        assert any(m.path == "status_code" for m in result.mismatches)

    def test_body_field_changed(self):
        snapshot = {"status_code": 200, "headers": {}, "body": {"name": "old"}}
        response = ResponseData(
            status_code=200, headers={}, body={"name": "new"}, elapsed_ms=10,
        )
        result = compare_snapshot("suite", "test", snapshot, response)
        assert not result.matched
        assert result.mismatches[0].path == "body.name"
        assert result.mismatches[0].expected == "old"
        assert result.mismatches[0].actual == "new"

    def test_body_field_added(self):
        snapshot = {"status_code": 200, "headers": {}, "body": {"a": 1}}
        response = ResponseData(
            status_code=200, headers={}, body={"a": 1, "b": 2}, elapsed_ms=10,
        )
        result = compare_snapshot("suite", "test", snapshot, response)
        assert not result.matched
        assert any(m.path == "body.b" for m in result.mismatches)

    def test_body_field_removed(self):
        snapshot = {"status_code": 200, "headers": {}, "body": {"a": 1, "b": 2}}
        response = ResponseData(
            status_code=200, headers={}, body={"a": 1}, elapsed_ms=10,
        )
        result = compare_snapshot("suite", "test", snapshot, response)
        assert not result.matched
        assert any(m.path == "body.b" for m in result.mismatches)

    def test_nested_body_diff(self):
        snapshot = {"status_code": 200, "headers": {}, "body": {"user": {"role": "admin"}}}
        response = ResponseData(
            status_code=200, headers={}, body={"user": {"role": "viewer"}}, elapsed_ms=10,
        )
        result = compare_snapshot("suite", "test", snapshot, response)
        assert not result.matched
        assert result.mismatches[0].path == "body.user.role"
