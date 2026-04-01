"""Assertion engine for evaluating responses against expectations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jsonschema

from api_contract_tester.executor import ResponseData
from api_contract_tester.models import ExpectDefinition
from api_contract_tester.utils import resolve_dot_path


@dataclass
class AssertionResult:
    passed: bool
    message: str


def assert_status(expected: int, actual: int) -> AssertionResult:
    if expected == actual:
        return AssertionResult(True, f"Status {actual}")
    return AssertionResult(False, f"Expected status {expected}, got {actual}")


def assert_header(key: str, expected_value: str, actual_headers: dict[str, str]) -> AssertionResult:
    lower_headers = {k.lower(): v for k, v in actual_headers.items()}
    actual = lower_headers.get(key.lower())
    if actual is None:
        return AssertionResult(False, f"Header '{key}' not found in response")
    if expected_value.lower() in actual.lower():
        return AssertionResult(True, f"Header '{key}' matches")
    return AssertionResult(
        False, f"Header '{key}': expected '{expected_value}', got '{actual}'"
    )


def assert_body_field(path: str, expected: Any, body: Any) -> AssertionResult:
    if not isinstance(body, (dict, list)):
        return AssertionResult(False, f"Response body is not JSON (got {type(body).__name__})")

    found, actual = resolve_dot_path(body, path)

    if isinstance(expected, str) and expected == "exists":
        if found:
            return AssertionResult(True, f"Body '{path}' exists")
        return AssertionResult(False, f"Body '{path}' does not exist")

    if isinstance(expected, str) and expected.startswith("contains:"):
        substring = expected[len("contains:"):]
        if not found:
            return AssertionResult(False, f"Body '{path}' does not exist")
        if isinstance(actual, str) and substring in actual:
            return AssertionResult(True, f"Body '{path}' contains '{substring}'")
        return AssertionResult(
            False, f"Body '{path}': expected to contain '{substring}', got '{actual}'"
        )

    if isinstance(expected, str) and expected.startswith("gt:"):
        threshold = _parse_number(expected[3:])
        if threshold is None:
            return AssertionResult(False, f"Body '{path}': invalid gt threshold '{expected[3:]}'")
        if not found:
            return AssertionResult(False, f"Body '{path}' does not exist")
        if isinstance(actual, (int, float)) and actual > threshold:
            return AssertionResult(True, f"Body '{path}' {actual} > {threshold}")
        return AssertionResult(False, f"Body '{path}': expected > {threshold}, got {actual!r}")

    if isinstance(expected, str) and expected.startswith("lt:"):
        threshold = _parse_number(expected[3:])
        if threshold is None:
            return AssertionResult(False, f"Body '{path}': invalid lt threshold '{expected[3:]}'")
        if not found:
            return AssertionResult(False, f"Body '{path}' does not exist")
        if isinstance(actual, (int, float)) and actual < threshold:
            return AssertionResult(True, f"Body '{path}' {actual} < {threshold}")
        return AssertionResult(False, f"Body '{path}': expected < {threshold}, got {actual!r}")

    if isinstance(expected, str) and expected.startswith("regex:"):
        import re
        pattern = expected[6:]
        if not found:
            return AssertionResult(False, f"Body '{path}' does not exist")
        if isinstance(actual, str) and re.search(pattern, actual):
            return AssertionResult(True, f"Body '{path}' matches regex '{pattern}'")
        return AssertionResult(
            False, f"Body '{path}': regex '{pattern}' did not match '{actual}'"
        )

    if not found:
        return AssertionResult(False, f"Body '{path}' does not exist")

    if actual == expected:
        return AssertionResult(True, f"Body '{path}' == {expected!r}")
    return AssertionResult(
        False, f"Body '{path}': expected {expected!r}, got {actual!r}"
    )


def _parse_number(s: str) -> int | float | None:
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def assert_response_time(max_ms: int, actual_ms: float) -> AssertionResult:
    if actual_ms <= max_ms:
        return AssertionResult(True, f"Response time {actual_ms:.0f}ms <= {max_ms}ms")
    return AssertionResult(
        False, f"Response time {actual_ms:.0f}ms exceeded {max_ms}ms"
    )


def assert_json_schema(schema: dict[str, Any], body: Any) -> AssertionResult:
    """Validate response body against a JSON Schema."""
    try:
        jsonschema.validate(instance=body, schema=schema)
        return AssertionResult(True, "JSON Schema valid")
    except jsonschema.ValidationError as e:
        return AssertionResult(False, f"JSON Schema: {e.message}")
    except jsonschema.SchemaError as e:
        return AssertionResult(False, f"Invalid JSON Schema definition: {e.message}")


@dataclass
class TestResult:
    test_name: str
    passed: bool
    assertions: list[AssertionResult]
    elapsed_ms: float
    error: str | None = None
    suite_name: str = ""


def evaluate(
    test_name: str,
    expect: ExpectDefinition,
    response: ResponseData,
    suite_name: str = "",
) -> TestResult:
    """Run all assertions for a test against its response."""
    if response.error:
        return TestResult(
            test_name=test_name,
            passed=False,
            assertions=[],
            elapsed_ms=response.elapsed_ms,
            error=response.error,
            suite_name=suite_name,
        )

    results: list[AssertionResult] = []

    if expect.status is not None:
        results.append(assert_status(expect.status, response.status_code))

    for key, value in expect.headers.items():
        results.append(assert_header(key, value, response.headers))

    for path, expected in expect.body.items():
        results.append(assert_body_field(path, expected, response.body))

    if expect.max_response_time_ms is not None:
        results.append(assert_response_time(expect.max_response_time_ms, response.elapsed_ms))

    if expect.schema_def is not None:
        results.append(assert_json_schema(expect.schema_def, response.body))

    all_passed = all(r.passed for r in results)
    return TestResult(
        test_name=test_name,
        passed=all_passed,
        assertions=results,
        elapsed_ms=response.elapsed_ms,
        suite_name=suite_name,
    )
