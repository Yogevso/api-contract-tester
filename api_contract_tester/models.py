"""Typed models for test definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetryConfig(BaseModel):
    count: int = 0
    delay_ms: int = 500


class RequestDefinition(BaseModel):
    method: str = "GET"
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | list | None = Field(default=None, alias="json")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def normalize_method(self):
        self.method = self.method.upper()
        return self


class ExpectDefinition(BaseModel):
    status: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)
    max_response_time_ms: int | None = None
    schema_def: dict[str, Any] | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


class TestDefinition(BaseModel):
    name: str
    request: RequestDefinition
    expect: ExpectDefinition = Field(default_factory=ExpectDefinition)
    extract: dict[str, str] = Field(default_factory=dict)
    retry: RetryConfig = Field(default_factory=RetryConfig)


class TestSuite(BaseModel):
    suite: str = "default"
    tests: list[TestDefinition]

    @model_validator(mode="after")
    def require_tests(self):
        if not self.tests:
            raise ValueError("Suite must contain at least one test")
        return self
