"""Tests for the reporter module."""

from __future__ import annotations

import json
from xml.etree.ElementTree import fromstring

from api_contract_tester.assertions import AssertionResult, TestResult
from api_contract_tester.reporter import (
    generate_json_report,
    generate_junit_report,
    should_exit_failure,
)


def _make_result(name, passed, elapsed_ms=50, error=None, suite_name="suite"):
    assertions = [AssertionResult(passed=passed, message=f"{'Pass' if passed else 'Fail'}")]
    return TestResult(
        test_name=name,
        passed=passed,
        assertions=assertions,
        elapsed_ms=elapsed_ms,
        error=error,
        suite_name=suite_name,
    )


class TestShouldExitFailure:
    def test_all_pass(self):
        results = [_make_result("a", True), _make_result("b", True)]
        assert not should_exit_failure(results)

    def test_one_fail(self):
        results = [_make_result("a", True), _make_result("b", False)]
        assert should_exit_failure(results)

    def test_empty(self):
        assert not should_exit_failure([])


class TestJsonReport:
    def test_structure(self):
        results = [_make_result("test1", True), _make_result("test2", False, error="timeout")]
        report = json.loads(generate_json_report(results, 100.0))

        assert report["summary"]["total"] == 2
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 1
        assert report["summary"]["time_ms"] == 100.0
        assert len(report["tests"]) == 2
        assert report["tests"][0]["passed"] is True
        assert report["tests"][1]["error"] == "timeout"

    def test_empty_results(self):
        report = json.loads(generate_json_report([], 0))
        assert report["summary"]["total"] == 0


class TestJunitReport:
    def test_valid_xml(self):
        results = [_make_result("test1", True), _make_result("test2", False)]
        xml_str = generate_junit_report(results, 100.0)
        root = fromstring(xml_str)
        assert root.tag == "testsuites"

        suite = root.find("testsuite")
        assert suite is not None
        assert suite.get("tests") == "2"
        assert suite.get("failures") == "1"

    def test_failure_element(self):
        results = [_make_result("fail_test", False, error="Connection error")]
        xml_str = generate_junit_report(results, 50.0)
        root = fromstring(xml_str)

        testcase = root.find(".//testcase[@name='fail_test']")
        assert testcase is not None
        failure = testcase.find("failure")
        assert failure is not None
        assert "Connection error" in failure.text

    def test_passing_no_failure_element(self):
        results = [_make_result("pass_test", True)]
        xml_str = generate_junit_report(results, 50.0)
        root = fromstring(xml_str)
        testcase = root.find(".//testcase[@name='pass_test']")
        assert testcase is not None
        assert testcase.find("failure") is None
