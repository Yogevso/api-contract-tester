"""Tests for the CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from api_contract_tester.cli import app
from api_contract_tester.exit_codes import ExitCode

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestCLI:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "api-contract-tester" in result.output

    def test_run_help(self):
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--base-url" in result.output
        assert "--json-report" in result.output
        assert "--junit-report" in result.output
        assert "--dry-run" in result.output
        assert "--list" in result.output
        assert "--parallel" in result.output
        assert "--snapshot" in result.output
        assert "--compare-snapshot" in result.output

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "v0.1.0" in result.output

    def test_missing_path(self):
        result = runner.invoke(app, ["run", "/nonexistent/path"])
        assert result.exit_code == ExitCode.CONFIG_ERROR

    def test_invalid_file(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("not: a: valid: test: file")
        result = runner.invoke(app, ["run", str(f)])
        assert result.exit_code == ExitCode.CONFIG_ERROR


class TestValidateCommand:
    def test_validate_valid_files(self):
        result = runner.invoke(app, ["validate", str(FIXTURES)])
        assert result.exit_code == 0
        assert "valid" in result.output

    def test_validate_invalid_file(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("invalid: yaml: file: content")
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == ExitCode.CONFIG_ERROR

    def test_validate_missing_path(self):
        result = runner.invoke(app, ["validate", "/nonexistent/path"])
        assert result.exit_code == ExitCode.CONFIG_ERROR

    def test_validate_shows_test_names(self):
        result = runner.invoke(app, ["validate", str(FIXTURES / "sample_suite.yaml")])
        assert result.exit_code == 0
        assert "basic GET test" in result.output


class TestInitCommand:
    def test_init_creates_file(self, tmp_path):
        out = tmp_path / "tests" / "example.yaml"
        result = runner.invoke(app, ["init", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text()
        assert "suite:" in content
        assert "extract:" in content

    def test_init_refuses_overwrite(self, tmp_path):
        out = tmp_path / "existing.yaml"
        out.write_text("existing content")
        result = runner.invoke(app, ["init", str(out)])
        assert result.exit_code == 1
        assert "already exists" in result.output


class TestListFlag:
    def test_list_shows_tests(self):
        result = runner.invoke(app, ["run", str(FIXTURES), "--list"])
        assert result.exit_code == 0
        assert "basic GET test" in result.output

    def test_list_shows_method_and_path(self):
        result = runner.invoke(app, ["run", str(FIXTURES / "sample_suite.yaml"), "--list"])
        assert result.exit_code == 0
        assert "GET" in result.output
        assert "/status" in result.output

    def test_list_shows_suite_count(self):
        result = runner.invoke(app, ["run", str(FIXTURES), "--list"])
        assert result.exit_code == 0
        assert "suite" in result.output.lower()


class TestDryRunFlag:
    def test_dry_run_shows_plan(self):
        result = runner.invoke(app, ["run", str(FIXTURES), "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_dry_run_shows_url(self):
        result = runner.invoke(app, ["run", str(FIXTURES), "--dry-run", "--base-url", "http://example.com"])
        assert result.exit_code == 0
        assert "example.com" in result.output

    def test_dry_run_no_requests(self):
        # Should succeed even with an unreachable base URL
        result = runner.invoke(app, ["run", str(FIXTURES), "--dry-run", "--base-url", "http://0.0.0.0:1"])
        assert result.exit_code == 0
        assert "Dry run" in result.output


class TestDiffCommand:
    def test_diff_help(self):
        result = runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0
        assert "--base-url" in result.output
        assert "--compare-url" in result.output

    def test_diff_missing_path(self):
        result = runner.invoke(
            app, ["diff", "/nonexistent", "--base-url", "http://a", "--compare-url", "http://b"]
        )
        assert result.exit_code == ExitCode.CONFIG_ERROR
