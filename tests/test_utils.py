"""Tests for utility helpers."""

from __future__ import annotations

from api_contract_tester.utils import (
    deep_substitute,
    resolve_dot_path,
    substitute_env_vars,
    substitute_vars,
)


class TestSubstituteEnvVars:
    def test_basic_substitution(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "hello")
        assert substitute_env_vars("${MY_VAR}") == "hello"

    def test_dollar_syntax(self, monkeypatch):
        monkeypatch.setenv("TOKEN", "abc")
        assert substitute_env_vars("Bearer $TOKEN") == "Bearer abc"

    def test_unset_var_unchanged(self):
        result = substitute_env_vars("${UNSET_VAR_12345}")
        assert result == "${UNSET_VAR_12345}"

    def test_mixed_text(self, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        assert substitute_env_vars("http://${HOST}:8080") == "http://localhost:8080"

    def test_no_vars(self):
        assert substitute_env_vars("plain text") == "plain text"


class TestSubstituteVars:
    def test_from_variables(self):
        assert substitute_vars("${token}", {"token": "abc"}) == "abc"

    def test_falls_through_to_env(self, monkeypatch):
        monkeypatch.setenv("ENV_VAR", "from_env")
        assert substitute_vars("${ENV_VAR}", {}) == "from_env"

    def test_variable_takes_priority(self, monkeypatch):
        monkeypatch.setenv("VAR", "env_val")
        assert substitute_vars("${VAR}", {"VAR": "var_val"}) == "var_val"

    def test_non_string_value(self):
        assert substitute_vars("id=${id}", {"id": 42}) == "id=42"


class TestDeepSubstitute:
    def test_string(self):
        assert deep_substitute("${x}", {"x": "1"}) == "1"

    def test_dict(self):
        result = deep_substitute({"a": "${x}", "b": "static"}, {"x": "val"})
        assert result == {"a": "val", "b": "static"}

    def test_list(self):
        result = deep_substitute(["${x}", "y"], {"x": "z"})
        assert result == ["z", "y"]

    def test_nested(self):
        data = {"outer": {"inner": "${v}"}}
        assert deep_substitute(data, {"v": "ok"}) == {"outer": {"inner": "ok"}}

    def test_non_string_passthrough(self):
        assert deep_substitute(42, {}) == 42
        assert deep_substitute(None, {}) is None


class TestResolveDotPath:
    def test_simple_key(self):
        found, val = resolve_dot_path({"a": 1}, "a")
        assert found and val == 1

    def test_nested_key(self):
        found, val = resolve_dot_path({"a": {"b": 2}}, "a.b")
        assert found and val == 2

    def test_list_index(self):
        found, val = resolve_dot_path({"items": [10, 20, 30]}, "items.1")
        assert found and val == 20

    def test_missing_key(self):
        found, val = resolve_dot_path({"a": 1}, "b")
        assert not found

    def test_missing_nested(self):
        found, val = resolve_dot_path({"a": {"b": 1}}, "a.c")
        assert not found

    def test_list_index_out_of_range(self):
        found, val = resolve_dot_path({"items": [1]}, "items.5")
        assert not found

    def test_list_index_non_numeric(self):
        found, val = resolve_dot_path({"items": [1]}, "items.abc")
        assert not found

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        found, val = resolve_dot_path(data, "a.b.c.d")
        assert found and val == "deep"
