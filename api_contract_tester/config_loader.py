"""Load and validate test definition files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from api_contract_tester.models import TestSuite


SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}


def load_file(path: Path) -> TestSuite:
    """Parse a single test file into a TestSuite."""
    if not path.exists():
        raise FileNotFoundError(f"Test file not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Use .yaml, .yml, or .json")

    text = path.read_text(encoding="utf-8")

    if ext == ".json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e
    else:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"Test file must be a mapping, got {type(raw).__name__} in {path}")

    try:
        return TestSuite.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Invalid test definition in {path}:\n{e}") from e


def discover_files(path: Path) -> list[Path]:
    """Return sorted list of test files under a path (file or directory)."""
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {path.suffix}")
        return [path]

    if path.is_dir():
        files = sorted(
            f for f in path.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if not files:
            raise FileNotFoundError(f"No test files found in {path}")
        return files

    raise FileNotFoundError(f"Path does not exist: {path}")


def load_all(path: Path) -> list[TestSuite]:
    """Load all test suites from a file or directory."""
    files = discover_files(path)
    suites = []
    for f in files:
        suites.append(load_file(f))
    return suites
