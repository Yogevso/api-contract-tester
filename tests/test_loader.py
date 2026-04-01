"""Tests for config_loader module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from api_contract_tester.config_loader import discover_files, load_all, load_file
from api_contract_tester.models import TestSuite

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadFile:
    def test_load_yaml(self):
        suite = load_file(FIXTURES / "sample_suite.yaml")
        assert isinstance(suite, TestSuite)
        assert suite.suite == "sample-suite"
        assert len(suite.tests) == 2

    def test_load_json(self):
        suite = load_file(FIXTURES / "sample_suite.json")
        assert isinstance(suite, TestSuite)
        assert suite.suite == "sample-suite-json"
        assert len(suite.tests) == 1

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_file(Path("/nonexistent/file.yaml"))

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_file(f)

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("{{invalid yaml")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_file(f)

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{bad json")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_file(f)

    def test_missing_tests_field(self, tmp_path):
        f = tmp_path / "no_tests.yaml"
        f.write_text(yaml.dump({"suite": "empty"}))
        with pytest.raises(ValueError, match="Invalid test definition"):
            load_file(f)

    def test_empty_tests_list(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text(yaml.dump({"suite": "empty", "tests": []}))
        with pytest.raises(ValueError, match="at least one test"):
            load_file(f)

    def test_non_mapping_file(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text(yaml.dump([1, 2, 3]))
        with pytest.raises(ValueError, match="must be a mapping"):
            load_file(f)


class TestDiscoverFiles:
    def test_single_file(self):
        files = discover_files(FIXTURES / "sample_suite.yaml")
        assert len(files) == 1

    def test_directory(self):
        files = discover_files(FIXTURES)
        assert len(files) >= 2
        assert all(f.suffix in {".yaml", ".yml", ".json"} for f in files)

    def test_sorted_order(self):
        files = discover_files(FIXTURES)
        assert files == sorted(files)

    def test_nonexistent_path(self):
        with pytest.raises(FileNotFoundError):
            discover_files(Path("/does/not/exist"))

    def test_empty_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No test files"):
            discover_files(tmp_path)


class TestLoadAll:
    def test_load_directory(self):
        suites = load_all(FIXTURES)
        assert len(suites) >= 2
        assert all(isinstance(s, TestSuite) for s in suites)
