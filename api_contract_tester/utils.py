"""Utility helpers."""

from __future__ import annotations

import os
import re
from typing import Any


def substitute_env_vars(value: str) -> str:
    """Replace ${VAR} or $VAR patterns with environment variable values."""
    def _replace(match: re.Match) -> str:
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, match.group(0))

    return re.sub(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)", _replace, value)


def substitute_vars(value: str, variables: dict[str, Any]) -> str:
    """Replace ${var_name} patterns with values from the variables store.

    Applies variable substitution first, then falls through to env vars.
    """
    def _replace(match: re.Match) -> str:
        var_name = match.group(1) or match.group(2)
        if var_name in variables:
            return str(variables[var_name])
        return os.environ.get(var_name, match.group(0))

    return re.sub(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)", _replace, value)


def deep_substitute(data: Any, variables: dict[str, Any]) -> Any:
    """Recursively substitute variables in strings within dicts, lists, and scalars."""
    if isinstance(data, str):
        return substitute_vars(data, variables)
    if isinstance(data, dict):
        return {k: deep_substitute(v, variables) for k, v in data.items()}
    if isinstance(data, list):
        return [deep_substitute(item, variables) for item in data]
    return data


def resolve_dot_path(data: dict | list, path: str) -> tuple[bool, Any]:
    """Traverse a nested dict/list using dot-separated path. Returns (found, value)."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return False, None
        else:
            return False, None
    return True, current
