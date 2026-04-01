"""HTTP request executor with async support and variable extraction."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from api_contract_tester.models import TestDefinition
from api_contract_tester.utils import deep_substitute, resolve_dot_path, substitute_vars


@dataclass
class ResponseData:
    """Normalized response from an HTTP request."""
    status_code: int
    headers: dict[str, str]
    body: Any
    elapsed_ms: float
    error: str | None = None


@dataclass
class ExecutionContext:
    """Runtime context for test execution."""
    base_url: str = "http://localhost:8000"
    timeout: float = 10.0
    headers: dict[str, str] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)


async def execute_test(
    test: TestDefinition,
    ctx: ExecutionContext,
    client: httpx.AsyncClient,
) -> ResponseData:
    """Execute a single test definition and return the response data."""
    variables = ctx.variables

    url = ctx.base_url.rstrip("/") + "/" + test.request.path.lstrip("/")
    url = substitute_vars(url, variables)

    merged_headers = {**ctx.headers, **test.request.headers}
    merged_headers = {k: substitute_vars(v, variables) for k, v in merged_headers.items()}

    params = {k: substitute_vars(v, variables) for k, v in test.request.params.items()}

    json_body = deep_substitute(test.request.json_body, variables)

    last_error: str | None = None
    attempts = 1 + test.retry.count

    for attempt in range(attempts):
        if attempt > 0:
            await asyncio.sleep(test.retry.delay_ms / 1000)

        try:
            start = time.perf_counter()
            response = await client.request(
                method=test.request.method,
                url=url,
                headers=merged_headers,
                params=params,
                json=json_body,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            try:
                body = response.json()
            except Exception:
                body = response.text

            return ResponseData(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=body,
                elapsed_ms=elapsed_ms,
            )

        except httpx.TimeoutException:
            last_error = f"Request timed out after {ctx.timeout}s"
        except httpx.ConnectError as e:
            last_error = f"Connection error: {e}"
        except httpx.HTTPError as e:
            last_error = f"HTTP error: {e}"

    return ResponseData(
        status_code=0,
        headers={},
        body=None,
        elapsed_ms=0,
        error=last_error
        + (f" (after {attempts} attempts)" if attempts > 1 else ""),
    )


def extract_variables(
    test: TestDefinition,
    response: ResponseData,
    variables: dict[str, Any],
) -> None:
    """Extract variables from a response body into the shared variable store."""
    if not test.extract or not isinstance(response.body, (dict, list)):
        return
    for var_name, body_path in test.extract.items():
        found, value = resolve_dot_path(response.body, body_path)
        if found:
            variables[var_name] = value
