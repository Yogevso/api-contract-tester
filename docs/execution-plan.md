# Execution Plan

## Architecture

### High-Level Flow

```
CLI entry
  └── load config path
        ├── parse files
        ├── validate definitions
        ├── build execution plan
        ├── execute requests
        ├── evaluate assertions
        └── print report + exit code
```

### Main Modules

1. **CLI layer** — argument parsing, command dispatch, exit codes
2. **Config loader** — loading JSON/YAML, directory traversal, env var substitution
3. **Schema / models** — typed test definitions, internal validation
4. **HTTP executor** — sending requests, timeout handling, timing, response normalization
5. **Assertion engine** — status, header, body path, response time, optional schema validation
6. **Reporter** — terminal output, summaries, failure formatting

## CLI Design

### Main Command

```
api-contract-tester run <path>
```

### Flags

| Flag | Description |
|------|-------------|
| `--base-url` | Override base URL for all requests |
| `--timeout` | Request timeout in seconds (default: 10) |
| `--fail-fast` | Stop on first failure |
| `--verbose` | Show request/response details |
| `--help` | Show help |

### Help

```
api-contract-tester --help
api-contract-tester run --help
```

## Test File Format

### YAML Example

```yaml
suite: auth-tests
tests:
  - name: login success
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
      headers:
        Content-Type: application/json
      body:
        token: exists
      max_response_time_ms: 500

  - name: login invalid password
    request:
      method: POST
      path: /auth/login
      headers:
        Content-Type: application/json
      json:
        email: test@example.com
        password: wrong
    expect:
      status: 401
```

### Body Assertion Style

- `exists` — field must be present
- Exact value — field must equal value
- `contains:<substring>` — field must contain substring

## File Structure

```
api-contract-tester/
├── api_contract_tester/
│   ├── __init__.py
│   ├── cli.py
│   ├── config_loader.py
│   ├── executor.py
│   ├── assertions.py
│   ├── models.py
│   ├── reporter.py
│   ├── utils.py
│   └── exit_codes.py
├── tests/
│   ├── test_cli.py
│   ├── test_loader.py
│   ├── test_assertions.py
│   ├── test_executor.py
│   └── fixtures/
│       ├── sample_suite.yaml
│       └── sample_suite.json
├── examples/
│   ├── auth.yaml
│   └── users.yaml
├── docs/
│   ├── prd.md
│   └── execution-plan.md
├── README.md
├── pyproject.toml
├── .gitignore
├── LICENSE
└── .github/
    └── workflows/
        └── ci.yml
```

## Phases

### Phase 1 — Foundation

**Goal:** Create the project skeleton and CLI entry.

- Initialize Python project with pyproject.toml
- Add CLI entrypoint with typer
- Setup lint/test tooling
- Create package structure

**Exit criteria:** project installs locally, CLI runs `--help` successfully.

### Phase 2 — Config Models and Parsing

**Goal:** Load and validate test definitions.

- Define typed models with pydantic
- Support YAML and JSON input
- Validate required fields
- Support file and directory loading
- Deterministic ordering

**Exit criteria:** valid files parse into internal models, malformed files fail clearly.

### Phase 3 — HTTP Execution

**Goal:** Execute test requests reliably.

- Build HTTP client wrapper with httpx
- Support method, path, headers, params, json body
- Support base URL override
- Collect response timing
- Normalize response object

**Exit criteria:** requests execute correctly, timeout behavior is controlled.

### Phase 4 — Assertion Engine

**Goal:** Evaluate responses against expected behavior.

- Status assertion
- Header assertion
- Body path assertions (exists, equality, contains)
- Max response time assertion

**Exit criteria:** core assertions pass/fail correctly, failures identify exact mismatch.

### Phase 5 — Reporting and Exit Codes

**Goal:** Make output clean and CI-friendly.

- Per-test pass/fail output
- Summary totals
- Suite-level timing
- Failure details
- Exit code handling

**Exit criteria:** human-readable output, CI can rely on exit codes.

### Phase 6 — Examples and Usability Polish

**Goal:** Make the tool feel real and usable.

- Example suites
- Better help text
- `--verbose` and `--fail-fast` flags
- Formatting cleanup

**Exit criteria:** new user can run example suite immediately.

### Phase 7 — Testing and Packaging

**Goal:** Make the repo strong and trustworthy.

- Unit tests for loader, assertions, executor
- Integration test with mocked HTTP
- GitHub Actions CI
- README documentation
- Packaging cleanup

**Exit criteria:** repo is portfolio-ready, install + run path documented.

## Tech Stack

| Component | Library |
|-----------|---------|
| CLI | typer |
| HTTP | httpx |
| Models | pydantic |
| YAML | pyyaml |
| Tests | pytest |
