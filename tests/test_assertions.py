"""Tests for the assertion engine."""

from __future__ import annotations

import pytest

from api_contract_tester.assertions import (
    AssertionResult,
    assert_body_field,
    assert_header,
    assert_json_schema,
    assert_response_time,
    assert_status,
    evaluate,
)
from api_contract_tester.executor import ResponseData
from api_contract_tester.models import ExpectDefinition


class TestAssertStatus:
    def test_match(self):
        r = assert_status(200, 200)
        assert r.passed

    def test_mismatch(self):
        r = assert_status(200, 404)
        assert not r.passed
        assert "404" in r.message


class TestAssertHeader:
    def test_present_match(self):
        r = assert_header("Content-Type", "application/json", {"Content-Type": "application/json"})
        assert r.passed

    def test_case_insensitive(self):
        r = assert_header("content-type", "application/json", {"Content-Type": "application/json"})
        assert r.passed

    def test_missing_header(self):
        r = assert_header("X-Custom", "value", {"Content-Type": "text/html"})
        assert not r.passed
        assert "not found" in r.message

    def test_value_mismatch(self):
        r = assert_header("Content-Type", "application/xml", {"Content-Type": "text/html"})
        assert not r.passed


class TestAssertBodyField:
    def test_exact_match(self):
        r = assert_body_field("name", "Alice", {"name": "Alice"})
        assert r.passed

    def test_exact_mismatch(self):
        r = assert_body_field("name", "Alice", {"name": "Bob"})
        assert not r.passed

    def test_exists_present(self):
        r = assert_body_field("token", "exists", {"token": "abc123"})
        assert r.passed

    def test_exists_missing(self):
        r = assert_body_field("token", "exists", {"user": "test"})
        assert not r.passed

    def test_nested_path(self):
        body = {"user": {"role": "admin"}}
        r = assert_body_field("user.role", "admin", body)
        assert r.passed

    def test_nested_path_missing(self):
        body = {"user": {"name": "test"}}
        r = assert_body_field("user.role", "admin", body)
        assert not r.passed

    def test_contains_match(self):
        r = assert_body_field("msg", "contains:hello", {"msg": "say hello world"})
        assert r.passed

    def test_contains_mismatch(self):
        r = assert_body_field("msg", "contains:goodbye", {"msg": "hello"})
        assert not r.passed

    def test_non_json_body(self):
        r = assert_body_field("key", "value", "plain text")
        assert not r.passed
        assert "not JSON" in r.message

    def test_numeric_value(self):
        r = assert_body_field("count", 5, {"count": 5})
        assert r.passed

    def test_list_index(self):
        body = {"items": ["a", "b", "c"]}
        r = assert_body_field("items.1", "b", body)
        assert r.passed

    def test_gt_pass(self):
        r = assert_body_field("count", "gt:5", {"count": 10})
        assert r.passed

    def test_gt_fail(self):
        r = assert_body_field("count", "gt:10", {"count": 5})
        assert not r.passed

    def test_lt_pass(self):
        r = assert_body_field("count", "lt:10", {"count": 5})
        assert r.passed

    def test_lt_fail(self):
        r = assert_body_field("count", "lt:5", {"count": 10})
        assert not r.passed

    def test_regex_match(self):
        r = assert_body_field("email", r"regex:^[\w.]+@\w+\.\w+$", {"email": "a@b.com"})
        assert r.passed

    def test_regex_no_match(self):
        r = assert_body_field("email", r"regex:^\d+$", {"email": "not-a-number"})
        assert not r.passed


class TestAssertJsonSchema:
    def test_valid_schema(self):
        schema = {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
            },
        }
        r = assert_json_schema(schema, {"id": 1, "name": "test"})
        assert r.passed

    def test_invalid_body(self):
        schema = {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}},
        }
        r = assert_json_schema(schema, {"name": "no id"})
        assert not r.passed
        assert "id" in r.message

    def test_type_mismatch(self):
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}
        r = assert_json_schema(schema, {"age": "not a number"})
        assert not r.passed

    def test_bad_schema_definition(self):
        r = assert_json_schema({"type": "invalid_type"}, {"key": "val"})
        assert not r.passed


class TestAssertResponseTime:
    def test_within_limit(self):
        r = assert_response_time(500, 200.0)
        assert r.passed

    def test_exceeds_limit(self):
        r = assert_response_time(100, 250.0)
        assert not r.passed
        assert "exceeded" in r.message


class TestEvaluate:
    def test_all_pass(self):
        expect = ExpectDefinition(status=200, body={"name": "exists"})
        response = ResponseData(
            status_code=200, headers={}, body={"name": "test"}, elapsed_ms=50
        )
        result = evaluate("test", expect, response)
        assert result.passed

    def test_status_fail(self):
        expect = ExpectDefinition(status=200)
        response = ResponseData(status_code=500, headers={}, body={}, elapsed_ms=50)
        result = evaluate("test", expect, response)
        assert not result.passed

    def test_error_response(self):
        expect = ExpectDefinition(status=200)
        response = ResponseData(
            status_code=0, headers={}, body=None, elapsed_ms=0, error="Connection refused"
        )
        result = evaluate("test", expect, response)
        assert not result.passed
        assert result.error == "Connection refused"

    def test_empty_expect(self):
        expect = ExpectDefinition()
        response = ResponseData(status_code=200, headers={}, body={}, elapsed_ms=50)
        result = evaluate("test", expect, response)
        assert result.passed

    def test_schema_validation_pass(self):
        expect = ExpectDefinition(
            status=200,
            schema_def={"type": "object", "required": ["id"]},
        )
        response = ResponseData(
            status_code=200, headers={}, body={"id": 1}, elapsed_ms=50
        )
        result = evaluate("test", expect, response)
        assert result.passed

    def test_schema_validation_fail(self):
        expect = ExpectDefinition(
            status=200,
            schema_def={"type": "object", "required": ["id"]},
        )
        response = ResponseData(
            status_code=200, headers={}, body={"name": "no id"}, elapsed_ms=50
        )
        result = evaluate("test", expect, response)
        assert not result.passed

    def test_suite_name_preserved(self):
        expect = ExpectDefinition(status=200)
        response = ResponseData(status_code=200, headers={}, body={}, elapsed_ms=50)
        result = evaluate("test", expect, response, suite_name="my-suite")
        assert result.suite_name == "my-suite"
