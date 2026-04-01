"""Tests for the HTTP executor using pytest-httpserver."""

from __future__ import annotations

import json

import httpx
import pytest
from werkzeug.wrappers import Response

from api_contract_tester.executor import (
    ExecutionContext,
    ResponseData,
    execute_test,
    extract_variables,
)
from api_contract_tester.models import RequestDefinition, TestDefinition


@pytest.fixture
def ctx(httpserver):
    return ExecutionContext(
        base_url=httpserver.url_for(""),
        timeout=5.0,
    )


class TestExecutor:
    @pytest.mark.asyncio
    async def test_get_request(self, httpserver, ctx):
        httpserver.expect_request("/status").respond_with_json({"ok": True})
        test = TestDefinition(
            name="get status",
            request=RequestDefinition(method="GET", path="/status"),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.status_code == 200
        assert resp.body == {"ok": True}
        assert resp.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_post_with_json(self, httpserver, ctx):
        def handler(request):
            data = json.loads(request.data)
            return Response(
                json.dumps({"echo": data}),
                content_type="application/json",
                status=201,
            )

        httpserver.expect_request("/echo", method="POST").respond_with_handler(handler)

        test = TestDefinition(
            name="post echo",
            request=RequestDefinition(
                method="POST",
                path="/echo",
                headers={"Content-Type": "application/json"},
                json_body={"msg": "hello"},
            ),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.status_code == 201
        assert resp.body["echo"]["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_custom_headers(self, httpserver, ctx):
        def handler(request):
            auth = request.headers.get("Authorization", "")
            return Response(
                json.dumps({"auth": auth}),
                content_type="application/json",
            )

        httpserver.expect_request("/secure").respond_with_handler(handler)

        test = TestDefinition(
            name="auth header",
            request=RequestDefinition(
                method="GET",
                path="/secure",
                headers={"Authorization": "Bearer test-token"},
            ),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.body["auth"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_query_params(self, httpserver, ctx):
        httpserver.expect_request("/search", query_string="q=test").respond_with_json(
            {"results": []}
        )
        test = TestDefinition(
            name="search",
            request=RequestDefinition(method="GET", path="/search", params={"q": "test"}),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_connection_error(self):
        ctx = ExecutionContext(base_url="http://127.0.0.1:1", timeout=1.0)
        test = TestDefinition(
            name="bad conn",
            request=RequestDefinition(method="GET", path="/nope"),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.error is not None
        assert resp.status_code == 0

    @pytest.mark.asyncio
    async def test_non_json_response(self, httpserver, ctx):
        httpserver.expect_request("/text").respond_with_data(
            "plain text", content_type="text/plain"
        )
        test = TestDefinition(
            name="text response",
            request=RequestDefinition(method="GET", path="/text"),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.status_code == 200
        assert resp.body == "plain text"

    @pytest.mark.asyncio
    async def test_variable_substitution_in_url(self, httpserver, ctx):
        httpserver.expect_request("/users/42").respond_with_json({"id": 42})
        ctx.variables = {"user_id": "42"}
        test = TestDefinition(
            name="var sub",
            request=RequestDefinition(method="GET", path="/users/${user_id}"),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.status_code == 200
        assert resp.body["id"] == 42

    @pytest.mark.asyncio
    async def test_variable_substitution_in_json_body(self, httpserver, ctx):
        def handler(request):
            data = json.loads(request.data)
            return Response(
                json.dumps(data),
                content_type="application/json",
            )

        httpserver.expect_request("/echo", method="POST").respond_with_handler(handler)

        ctx.variables = {"token": "abc123"}
        test = TestDefinition(
            name="json var sub",
            request=RequestDefinition(
                method="POST",
                path="/echo",
                json_body={"auth": "${token}"},
            ),
        )
        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            resp = await execute_test(test, ctx, client)
        assert resp.body["auth"] == "abc123"


class TestExtractVariables:
    def test_extract_simple(self):
        test = TestDefinition(
            name="extract",
            request=RequestDefinition(method="GET", path="/x"),
            extract={"my_id": "id"},
        )
        response = ResponseData(
            status_code=200, headers={}, body={"id": 42, "name": "test"}, elapsed_ms=10
        )
        variables: dict = {}
        extract_variables(test, response, variables)
        assert variables["my_id"] == 42

    def test_extract_nested(self):
        test = TestDefinition(
            name="extract nested",
            request=RequestDefinition(method="GET", path="/x"),
            extract={"role": "user.role"},
        )
        response = ResponseData(
            status_code=200, headers={}, body={"user": {"role": "admin"}}, elapsed_ms=10
        )
        variables: dict = {}
        extract_variables(test, response, variables)
        assert variables["role"] == "admin"

    def test_extract_missing_path(self):
        test = TestDefinition(
            name="extract missing",
            request=RequestDefinition(method="GET", path="/x"),
            extract={"val": "nonexistent"},
        )
        response = ResponseData(
            status_code=200, headers={}, body={"id": 1}, elapsed_ms=10
        )
        variables: dict = {}
        extract_variables(test, response, variables)
        assert "val" not in variables

    def test_no_extract_on_non_json(self):
        test = TestDefinition(
            name="no extract",
            request=RequestDefinition(method="GET", path="/x"),
            extract={"val": "key"},
        )
        response = ResponseData(
            status_code=200, headers={}, body="plain text", elapsed_ms=10
        )
        variables: dict = {}
        extract_variables(test, response, variables)
        assert "val" not in variables
