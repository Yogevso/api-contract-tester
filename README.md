# api-contract-tester

A production-style CLI tool for validating HTTP API contracts through declarative test definitions.

Define requests, expected responses, and assertions in YAML or JSON. Run them against any API. Get clean pass/fail output with a progress bar, detailed failure messages, JSON/JUnit reports, and non-zero exit codes on failure — built for local development and CI pipelines.

This tool can be used to validate API changes before deployment, ensuring backward compatibility between environments.

## Headline Feature: Diff Mode

Compare API responses between two environments — staging vs production, v1 vs v2 — to detect breaking changes before release:

```bash
api-contract-tester diff tests/ \
  --base-url https://api.v1.example.com \
  --compare-url https://api.v2.example.com
```

```
 SAME  health check
 DIFF  get user
     status: 200 → 200
     user.name: "John" → "John Doe"
     user.email: <missing> → "john@example.com"

  ✔ 3 identical
  ✖ 1 different
```

## Features

- **Environment diff mode** — compare responses between two APIs side-by-side (staging vs production, v1 vs v2)
- **Snapshot testing** — save responses as baselines, detect regressions later
- **Parallel execution** — run independent tests concurrently with `--parallel N`
- **Declarative test files** — YAML or JSON, human-readable, version-controllable
- **Rich assertion engine** — status codes, headers, body fields (exact, exists, contains, regex, gt/lt), response time thresholds, JSON Schema validation
- **Test chaining** — extract values from responses and inject them into subsequent requests
- **Async execution** — built on `httpx.AsyncClient` for fast, non-blocking HTTP
- **Configurable retries** — per-test retry with configurable delay
- **Environment variables** — `${VAR}` substitution in URLs, headers, and request bodies
- **Multiple output formats** — terminal (Rich), JSON report, JUnit XML report
- **`--dry-run` and `--list`** — preview execution plan or list all tests without running
- **CI-ready** — deterministic exit codes, `--fail-fast`, report file output
- **Five CLI commands** — `run`, `diff`, `validate`, `init`, plus `--list` / `--dry-run` modes

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

**1. Scaffold a test file:**

```bash
api-contract-tester init tests/example.yaml
```

**2. Or create one manually** (`tests/health.yaml`):

```yaml
suite: health-check
tests:
  - name: API is up
    request:
      method: GET
      path: /health
    expect:
      status: 200
      body:
        status: ok
```

**3. Validate the file structure:**

```bash
api-contract-tester validate tests/health.yaml
```

**4. Run it:**

```bash
api-contract-tester run tests/health.yaml --base-url http://localhost:8000
```

**5. Or run a whole directory:**

```bash
api-contract-tester run tests/contracts/
```

## CLI Usage

### `run` — Execute tests

```
api-contract-tester run <path> [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--base-url`, `-b` | `http://localhost:8000` | Base URL for all requests |
| `--timeout`, `-t` | `10` | Request timeout in seconds |
| `--fail-fast` | `false` | Stop on first failure |
| `--verbose` | `false` | Show request details and all assertions |
| `--parallel`, `-p` | `1` | Number of concurrent tests per suite |
| `--json-report` | — | Write JSON report to file |
| `--junit-report` | — | Write JUnit XML report to file |
| `--dry-run` | `false` | Show execution plan without making requests |
| `--list` | `false` | List all tests without running them |
| `--snapshot` | `false` | Save responses as snapshots |
| `--compare-snapshot` | `false` | Compare responses against saved snapshots |

```bash
# CI pipeline usage
api-contract-tester run tests/ \
  --base-url https://api.staging.example.com \
  --fail-fast \
  --junit-report results.xml

# Preview what would run
api-contract-tester run tests/ --dry-run

# List all discovered tests
api-contract-tester run tests/ --list

# Run with parallelism
api-contract-tester run tests/ --parallel 5

# Snapshot: save baseline
api-contract-tester run tests/ --snapshot

# Snapshot: compare against baseline
api-contract-tester run tests/ --compare-snapshot
```

### `diff` — Compare two environments

```
api-contract-tester diff <path> --base-url <url1> --compare-url <url2> [OPTIONS]
```

Runs every test against **both** URLs concurrently, then shows a field-by-field diff of the responses. Useful for:

- **Migration validation** — v1 vs v2
- **Environment parity** — staging vs production
- **Breaking change detection** — before vs after deploy

```bash
api-contract-tester diff tests/ \
  --base-url https://api.v1.example.com \
  --compare-url https://api.v2.example.com
```

Output:

```
 SAME  health check
 DIFF  get user
     status: 200 → 200
     user.name: "John" → "John Doe"

  ✔ 1 identical
  ✖ 1 different
```

Exit code `1` if any differences are found — CI-friendly.

### `validate` — Check test files without running

```bash
api-contract-tester validate tests/
```

### `init` — Scaffold a starter test file

```bash
api-contract-tester init tests/my-api.yaml
```

## Test File Format

### Full Example with Chaining

```yaml
suite: auth-flow
tests:
  - name: login
    request:
      method: POST
      path: /auth/login
      headers:
        Content-Type: application/json
      json:
        email: test@example.com
        password: secret123
    expect:
      status: 200
      body:
        token: exists
        user.id: exists
      schema:
        type: object
        required: [token, user]
        properties:
          token: { type: string }
          user:
            type: object
            required: [id, email]
      max_response_time_ms: 500
    extract:
      auth_token: token
      user_id: user.id

  - name: get my profile
    request:
      method: GET
      path: /users/${user_id}
      headers:
        Authorization: Bearer ${auth_token}
    expect:
      status: 200
      body:
        email: "regex:^[\\w.]+@\\w+\\.\\w+$"

  - name: invalid login
    request:
      method: POST
      path: /auth/login
      json:
        email: test@example.com
        password: wrong
    expect:
      status: 401
    retry:
      count: 0
```

### Request Fields

| Field | Required | Description |
|-------|----------|-------------|
| `method` | No (default: GET) | HTTP method |
| `path` | Yes | URL path (appended to base URL) |
| `headers` | No | Request headers |
| `params` | No | Query parameters |
| `json` | No | JSON request body |

### Assertion Types

| Assertion | Example | Description |
|-----------|---------|-------------|
| Status code | `status: 200` | Exact status match |
| Header | `headers: { Content-Type: application/json }` | Header value contains match |
| Body exact | `body: { name: Alice }` | Field equals value |
| Body exists | `body: { token: exists }` | Field must be present |
| Body contains | `body: { msg: "contains:hello" }` | String contains substring |
| Body regex | `body: { email: "regex:^\\w+@" }` | String matches regex |
| Body gt/lt | `body: { age: "gt:18" }` | Numeric comparison |
| Nested path | `body: { user.role: admin }` | Dot-path into nested objects |
| List index | `body: { items.0.name: first }` | Index into arrays |
| Response time | `max_response_time_ms: 500` | Max response time in ms |
| JSON Schema | `schema: { type: object, required: [id] }` | Full JSON Schema validation |

### Variable Extraction & Chaining

Extract values from a response and use them in subsequent tests:

```yaml
tests:
  - name: create item
    request:
      method: POST
      path: /items
      json: { name: "widget" }
    expect:
      status: 201
    extract:
      item_id: id

  - name: get created item
    request:
      method: GET
      path: /items/${item_id}
    expect:
      status: 200
```

Variables are scoped per suite and resolved alongside environment variables.

### Retry Configuration

```yaml
tests:
  - name: flaky endpoint
    request:
      method: GET
      path: /sometimes-slow
    expect:
      status: 200
    retry:
      count: 2
      delay_ms: 1000
```

### Snapshot Testing

Save responses as baselines and compare later to detect regressions:

```bash
# Save baseline snapshots
api-contract-tester run tests/ --base-url http://localhost:8000 --snapshot

# Later, compare against baselines
api-contract-tester run tests/ --base-url http://localhost:8000 --compare-snapshot
```

Snapshots are saved to `.snapshots/` as JSON files, organized by suite and test name.

### Environment Variables

Use `${VAR}` syntax anywhere — URLs, headers, and JSON bodies:

```yaml
tests:
  - name: authenticated request
    request:
      method: GET
      path: /me
      headers:
        Authorization: Bearer ${API_TOKEN}
      json:
        org_id: ${ORG_ID}
    expect:
      status: 200
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All tests passed / all responses identical |
| `1` | One or more tests failed / differences found |
| `2` | Configuration error (bad file, missing path) |
| `3` | Runtime error |

## Architecture

```text
CLI (Typer)
  │
  ├── Config Loader (YAML/JSON → Pydantic models)
  ├── Executor (async HTTP via httpx)
  ├── Assertion Engine (status, headers, body, schema)
  ├── Diff Engine (compare responses across environments)
  ├── Snapshot Engine (save/load response baselines)
  └── Reporter (terminal, JSON, JUnit XML)
```

The system separates parsing, execution, validation, and reporting into distinct modules — keeping responsibilities clear and each layer independently testable.

## Project Structure

```
api-contract-tester/
├── api_contract_tester/
│   ├── cli.py              # Typer CLI (run, diff, validate, init)
│   ├── config_loader.py    # YAML/JSON parsing, file discovery
│   ├── models.py           # Pydantic models for test definitions
│   ├── executor.py         # Async HTTP execution, variable extraction
│   ├── assertions.py       # Assertion engine + JSON Schema validation
│   ├── reporter.py         # Rich terminal output, JSON/JUnit/diff/snapshot reports
│   ├── diff.py             # Response comparison engine (diff mode)
│   ├── snapshot.py         # Snapshot save/load/compare
│   ├── utils.py            # Env/var substitution, dot-path resolver
│   └── exit_codes.py       # Exit code constants (IntEnum)
├── tests/                  # 136 pytest tests
│   ├── test_assertions.py  # 37 tests — assertion types + schema
│   ├── test_cli.py         # 20 tests — all commands + flags
│   ├── test_diff.py        # 13 tests — diff engine
│   ├── test_executor.py    # 12 tests — async HTTP + extraction
│   ├── test_loader.py      # 15 tests — parsing, validation, discovery
│   ├── test_reporter.py    # 8 tests — report generation
│   ├── test_snapshot.py    # 12 tests — snapshot save/load/compare
│   ├── test_utils.py       # 21 tests — substitution + dot-path
│   └── fixtures/
├── examples/               # Ready-to-run example suites
├── docs/                   # PRD and execution plan
├── pyproject.toml
└── .github/workflows/ci.yml
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check .
```

## Tech Stack

| Component | Library |
|-----------|---------|
| CLI | [Typer](https://typer.tiangolo.com/) |
| HTTP | [HTTPX](https://www.python-httpx.org/) (async) |
| Models | [Pydantic v2](https://docs.pydantic.dev/) |
| Schema | [jsonschema](https://python-jsonschema.readthedocs.io/) |
| YAML | [PyYAML](https://pyyaml.org/) |
| Output | [Rich](https://rich.readthedocs.io/) |
| Tests | [pytest](https://pytest.org/) + pytest-asyncio + pytest-httpserver |

## Why This Project

This project demonstrates how to design a developer-facing tool for API validation and contract testing.

It focuses on:
- Clean CLI design with multiple commands and flags
- Structured, declarative test definitions (YAML/JSON → Pydantic)
- Async request execution with connection reuse
- Extensible assertion logic (exact, pattern, schema)
- Real-world use cases like environment comparison and regression detection

## License

MIT
