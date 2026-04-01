# Product Requirements Document

## Product

**Name:** `api-contract-tester`
**Type:** Developer CLI tool
**Primary Platform:** Command line

## 1. Overview

`api-contract-tester` is a command-line tool for validating HTTP API contracts through executable test definitions. It allows developers to define requests, expected responses, and assertions in structured files, then run them automatically against a target API.

The project exists to demonstrate developer tooling, API validation, and automation-focused engineering. It is designed as a lightweight alternative for common API smoke tests and contract checks in local development, CI pipelines, and backend integration workflows.

The goal is to build a tool that is simple to use, easy to extend, and professional enough to showcase testing discipline and product-minded engineering.

## 2. Goals

- Execute API tests from JSON or YAML configuration files
- Validate response status codes, headers, body fields, and optional schemas
- Provide clean, readable CLI output for pass/fail results
- Return non-zero exit codes when tests fail
- Support local usage and CI integration
- Package the project like a real developer tool

## 3. Design Principles

- Prefer clarity and usability over over-engineering
- Keep the test definition format human-readable
- Make failures easy to understand and debug
- Separate parsing, execution, validation, and reporting clearly
- Design the tool so it can grow without becoming complicated

## 4. Users

### Developer

Needs to:

- Verify API endpoints quickly
- Run repeatable contract tests locally
- Understand failures without reading code

### QA / Reviewer

Needs to:

- Run predefined API checks
- Validate expected responses
- Use the tool without changing implementation code

### CI Pipeline

Needs to:

- Run the tool non-interactively
- Fail fast when tests fail
- Produce predictable exit codes

## 5. Core Features

### Test File Input

- Load test definitions from JSON or YAML
- Support one file or a directory of test files
- Validate file structure before execution

### Request Execution

- Send HTTP requests using configured method, URL, headers, query params, and body
- Support common methods such as GET, POST, PUT, PATCH, DELETE
- Support configurable timeout

### Assertions

- Validate status code
- Validate selected response headers
- Validate response body fields by path
- Validate response time thresholds
- Optionally validate response body against a JSON schema

### Reporting

- Show pass/fail result per test
- Print failure reason clearly
- Show final summary with totals
- Return non-zero exit code on failure

### Configuration

- Allow base URL override from CLI
- Allow environment variable substitution
- Allow auth token/header injection through config or environment

## 6. Key Interaction Surface

The main interaction surface is the terminal:

- Run a file or directory of tests
- Inspect pass/fail output
- Inspect summary and failure details
- Use exit code in scripts or CI

## 7. User Flows

### Run a Single Test File

1. User runs the CLI with a path to a test definition file
2. Tool parses and validates the file
3. Tool executes each test in order
4. Tool validates responses against expected assertions
5. Tool prints results and final summary
6. Tool exits with code `0` if all tests pass, non-zero otherwise

### Run a Test Suite Directory

1. User points the CLI to a directory
2. Tool loads all supported test files
3. Tool executes them in deterministic order
4. Tool prints grouped results and final suite summary

### Debug a Failure

1. User runs a test suite
2. One or more tests fail
3. Tool prints assertion failure details
4. User identifies mismatch in status, body, header, or latency

## 8. Functional Requirements

### CLI

- `FR-1` The tool must accept a file or directory path as input
- `FR-2` The tool must support a `--base-url` override
- `FR-3` The tool must support configurable timeout
- `FR-4` The tool must return exit code `0` when all tests pass
- `FR-5` The tool must return non-zero exit code when one or more tests fail
- `FR-6` The tool must provide a `--help` command

### Parsing and Validation

- `FR-7` The tool must parse JSON test files
- `FR-8` The tool should parse YAML test files
- `FR-9` The tool must validate required fields before execution
- `FR-10` The tool must reject malformed test definitions with clear errors

### Request Execution

- `FR-11` The tool must execute HTTP requests defined in the test files
- `FR-12` The tool must support request headers
- `FR-13` The tool must support request query parameters
- `FR-14` The tool must support JSON request bodies

### Assertions

- `FR-15` The tool must validate expected status code
- `FR-16` The tool must validate selected response headers
- `FR-17` The tool must validate response body fields using path-based assertions
- `FR-18` The tool must support response time assertions
- `FR-19` The tool should support JSON schema validation

### Reporting

- `FR-20` The tool must print pass/fail per test
- `FR-21` The tool must print human-readable failure reasons
- `FR-22` The tool must print a final summary of passed/failed tests

## 9. Non-Functional Requirements

### Usability

- Output should be readable in a terminal without extra tooling
- Errors should explain what failed and where

### Reliability

- Test execution should be deterministic
- Invalid config should fail before making unnecessary requests

### Maintainability

- Parsing, execution, assertion, and reporting should be separated into clear modules
- The project should be easy to extend with new assertion types

### Performance

- The tool should be fast enough for local and CI use on small-to-medium suites
- Network timeout behavior should be explicit and configurable

## 10. Constraints

- Initial version should stay lightweight
- Scope should focus on HTTP APIs only
- Initial schema/assertion support should be practical, not exhaustive
- The tool should remain simple enough to explain in interviews

## 11. Out of Scope

- Full Postman-style collection management
- GUI
- Browser automation
- Load testing
- gRPC support
- Distributed test execution
- Very advanced scripting language inside test files

## 12. Success Criteria

- A user can define tests in config files and run them from the CLI
- The tool clearly validates status, body, and header expectations
- Failures are easy to understand
- The tool works in local development and CI
- The repository is clean, documented, and portfolio-ready
