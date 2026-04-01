"""CLI entry point."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from api_contract_tester import __version__
from api_contract_tester.assertions import TestResult, evaluate
from api_contract_tester.config_loader import load_all
from api_contract_tester.diff import compare_responses
from api_contract_tester.executor import ExecutionContext, execute_test, extract_variables
from api_contract_tester.exit_codes import ExitCode
from api_contract_tester.reporter import (
    generate_json_report,
    generate_junit_report,
    print_diff_result,
    print_diff_summary,
    print_result,
    print_snapshot_result,
    print_snapshot_summary,
    print_summary,
    should_exit_failure,
)
from api_contract_tester.snapshot import compare_snapshot, load_snapshot, save_snapshot

app = typer.Typer(
    name="api-contract-tester",
    help="Validate API contracts through declarative test definitions.",
    add_completion=False,
    pretty_exceptions_enable=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"api-contract-tester v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit.", callback=version_callback,
        is_eager=True,
    ),
):
    """api-contract-tester: validate API contracts from the command line."""


@app.command()
def run(
    path: str = typer.Argument(..., help="Path to a test file or directory of test files."),
    base_url: str = typer.Option(
        "http://localhost:8000", "--base-url", "-b", help="Base URL for all requests."
    ),
    timeout: float = typer.Option(
        10.0, "--timeout", "-t", help="Request timeout in seconds."
    ),
    fail_fast: bool = typer.Option(
        False, "--fail-fast", help="Stop on first test failure."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show request details and all assertions."
    ),
    parallel: int = typer.Option(
        1, "--parallel", "-p", help="Number of concurrent tests per suite.",
        min=1, max=50,
    ),
    json_report: Optional[str] = typer.Option(
        None, "--json-report", help="Write JSON report to this file path."
    ),
    junit_report: Optional[str] = typer.Option(
        None, "--junit-report", help="Write JUnit XML report to this file path."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would run without executing requests."
    ),
    list_tests: bool = typer.Option(
        False, "--list", help="List all tests without running them."
    ),
    snapshot: bool = typer.Option(
        False, "--snapshot", help="Save responses as snapshots for future comparison."
    ),
    compare_snapshot_flag: bool = typer.Option(
        False, "--compare-snapshot", help="Compare responses against saved snapshots."
    ),
):
    """Run API contract tests."""
    target = Path(path)

    try:
        suites = load_all(target)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

    total_tests = sum(len(s.tests) for s in suites)

    # --list: just print tests and exit
    if list_tests:
        _print_test_list(suites, total_tests)
        return

    # --dry-run: show plan and exit
    if dry_run:
        _print_dry_run(suites, base_url, total_tests)
        return

    ctx = ExecutionContext(base_url=base_url, timeout=timeout)

    try:
        all_results, total_time = asyncio.run(
            _run_suites(
                suites, ctx, fail_fast, verbose, total_tests,
                parallel=parallel,
                snapshot=snapshot,
                compare_snapshot_flag=compare_snapshot_flag,
                test_path=target,
            )
        )
    except Exception as e:
        console.print(f"[red]Runtime error:[/red] {e}")
        raise typer.Exit(code=ExitCode.RUNTIME_ERROR)

    print_summary(all_results, total_time)

    if json_report:
        report = generate_json_report(all_results, total_time)
        Path(json_report).write_text(report, encoding="utf-8")
        console.print(f"  JSON report written to [bold]{json_report}[/bold]")

    if junit_report:
        report = generate_junit_report(all_results, total_time)
        Path(junit_report).write_text(report, encoding="utf-8")
        console.print(f"  JUnit report written to [bold]{junit_report}[/bold]")

    if should_exit_failure(all_results):
        raise typer.Exit(code=ExitCode.TEST_FAILURE)


def _print_test_list(suites, total_tests):
    """Print all discovered tests without running them."""
    console.print(f"\n[bold]{total_tests} test(s) in {len(suites)} suite(s)[/bold]\n")
    for suite in suites:
        console.print(f"  [bold cyan]{suite.suite}[/bold cyan]")
        for test in suite.tests:
            extras = []
            if test.extract:
                extras.append("extract")
            if test.retry.count > 0:
                extras.append(f"retry:{test.retry.count}")
            tag = f"  [dim]({', '.join(extras)})[/dim]" if extras else ""
            console.print(
                f"    {test.request.method:6s} {test.request.path:30s}  "
                f"[dim]{test.name}[/dim]{tag}"
            )
    console.print()


def _print_dry_run(suites, base_url, total_tests):
    """Show execution plan without making HTTP calls."""
    console.print("\n[bold yellow]Dry run[/bold yellow] — no requests will be made\n")
    console.print(f"  Base URL:  [bold]{base_url}[/bold]")
    console.print(f"  Suites:    {len(suites)}")
    console.print(f"  Tests:     {total_tests}\n")

    for suite in suites:
        console.rule(f"[bold]{suite.suite}[/bold]")
        for test in suite.tests:
            url = base_url.rstrip("/") + "/" + test.request.path.lstrip("/")
            console.print(f"  [cyan]{test.request.method}[/cyan] {url}")
            console.print(f"    name: {test.name}")
            if test.expect.status is not None:
                console.print(f"    expect status: {test.expect.status}")
            if test.expect.body:
                console.print(f"    expect body checks: {len(test.expect.body)}")
            if test.extract:
                console.print(f"    extract: {', '.join(test.extract.keys())}")
        console.print()


async def _run_suites(
    suites, ctx, fail_fast, verbose, total_tests, *,
    parallel=1, snapshot=False, compare_snapshot_flag=False, test_path=None,
):
    """Execute all suites with an async HTTP client and progress bar."""
    all_results: list[TestResult] = []
    snapshot_results = []
    suite_start = time.perf_counter()
    stop = False

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running tests...", total=total_tests)

        async with httpx.AsyncClient(timeout=ctx.timeout) as client:
            for suite in suites:
                if stop:
                    break

                console.print()
                console.rule(f"[bold]{suite.suite}[/bold]")
                console.print()

                if parallel > 1 and not any(t.extract for t in suite.tests):
                    # Parallel: run batch of tests concurrently (only if no chaining)
                    sem = asyncio.Semaphore(parallel)

                    async def _run_one(td):
                        async with sem:
                            return td, await execute_test(td, ctx, client)

                    tasks = [_run_one(td) for td in suite.tests]
                    for coro in asyncio.as_completed(tasks):
                        test_def, response = await coro

                        result = evaluate(
                            test_def.name, test_def.expect, response, suite_name=suite.suite,
                        )
                        all_results.append(result)

                        _handle_snapshots(
                            snapshot, compare_snapshot_flag, test_path,
                            suite, test_def, response, snapshot_results,
                        )

                        request_info = _build_request_info(verbose, ctx, test_def, response)
                        print_result(result, verbose=verbose, request_info=request_info)
                        progress.advance(task)

                        if fail_fast and not result.passed:
                            console.print("\n[yellow]Stopping early (--fail-fast)[/yellow]")
                            stop = True
                            break
                else:
                    # Sequential: supports chaining via extract
                    for test_def in suite.tests:
                        if stop:
                            break

                        progress.update(task, description=f"Running: {test_def.name}")
                        response = await execute_test(test_def, ctx, client)

                        extract_variables(test_def, response, ctx.variables)

                        result = evaluate(
                            test_def.name, test_def.expect, response, suite_name=suite.suite,
                        )
                        all_results.append(result)

                        _handle_snapshots(
                            snapshot, compare_snapshot_flag, test_path,
                            suite, test_def, response, snapshot_results,
                        )

                        request_info = _build_request_info(verbose, ctx, test_def, response)
                        print_result(result, verbose=verbose, request_info=request_info)
                        progress.advance(task)

                        if fail_fast and not result.passed:
                            console.print("\n[yellow]Stopping early (--fail-fast)[/yellow]")
                            stop = True

    total_time = (time.perf_counter() - suite_start) * 1000

    # Print snapshot comparison results if comparing
    if compare_snapshot_flag and snapshot_results:
        console.print()
        console.rule("[bold]Snapshot Comparison[/bold]")
        console.print()
        for sr in snapshot_results:
            print_snapshot_result(sr)
        print_snapshot_summary(snapshot_results, total_time)

    if snapshot:
        console.print("\n  [green]✓[/green] Snapshots saved to [bold].snapshots/[/bold]")

    return all_results, total_time


def _build_request_info(verbose, ctx, test_def, response):
    """Build request info dict for verbose output."""
    if not verbose:
        return None
    url = ctx.base_url.rstrip("/") + "/" + test_def.request.path.lstrip("/")
    return {
        "method": test_def.request.method,
        "url": url,
        "status_code": response.status_code,
    }


def _handle_snapshots(
    snapshot, compare_snapshot_flag, test_path, suite, test_def, response, snapshot_results
):
    """Save or compare snapshots depending on flags."""
    if not test_path:
        return
    base_dir = test_path.parent if test_path.is_file() else test_path

    if snapshot:
        save_snapshot(base_dir, suite.suite, test_def.name, response)

    if compare_snapshot_flag:
        snap = load_snapshot(base_dir, suite.suite, test_def.name)
        if snap is None:
            from api_contract_tester.snapshot import SnapshotResult
            snapshot_results.append(SnapshotResult(
                test_name=test_def.name,
                suite_name=suite.suite,
                matched=False,
                snapshot_missing=True,
            ))
        else:
            snapshot_results.append(
                compare_snapshot(suite.suite, test_def.name, snap, response)
            )


@app.command()
def diff(
    path: str = typer.Argument(..., help="Path to a test file or directory."),
    base_url: str = typer.Option(
        ..., "--base-url", "-b", help="First environment URL."
    ),
    compare_url: str = typer.Option(
        ..., "--compare-url", "-c", help="Second environment URL to compare against."
    ),
    timeout: float = typer.Option(
        10.0, "--timeout", "-t", help="Request timeout in seconds."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show full diff details."
    ),
):
    """Compare API responses between two environments."""
    target = Path(path)

    try:
        suites = load_all(target)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

    total_tests = sum(len(s.tests) for s in suites)

    try:
        diffs, total_time = asyncio.run(
            _run_diff(suites, base_url, compare_url, timeout, total_tests)
        )
    except Exception as e:
        console.print(f"[red]Runtime error:[/red] {e}")
        raise typer.Exit(code=ExitCode.RUNTIME_ERROR)

    print_diff_summary(diffs, total_time)

    if any(not d.identical for d in diffs):
        raise typer.Exit(code=ExitCode.TEST_FAILURE)


async def _run_diff(suites, base_url, compare_url, timeout, total_tests):
    """Run each test against both URLs and compare responses."""
    diffs = []
    start = time.perf_counter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Comparing environments...", total=total_tests)

        async with httpx.AsyncClient(timeout=timeout) as client:
            ctx_left = ExecutionContext(base_url=base_url, timeout=timeout)
            ctx_right = ExecutionContext(base_url=compare_url, timeout=timeout)

            for suite in suites:
                console.print()
                console.rule(f"[bold]{suite.suite}[/bold]")
                console.print()

                for test_def in suite.tests:
                    progress.update(task, description=f"Comparing: {test_def.name}")

                    left, right = await asyncio.gather(
                        execute_test(test_def, ctx_left, client),
                        execute_test(test_def, ctx_right, client),
                    )

                    result = compare_responses(test_def.name, left, right)
                    diffs.append(result)

                    print_diff_result(result)
                    progress.advance(task)

    total_time = (time.perf_counter() - start) * 1000
    return diffs, total_time


@app.command()
def validate(
    path: str = typer.Argument(..., help="Path to a test file or directory to validate."),
):
    """Validate test files without executing requests."""
    target = Path(path)

    try:
        suites = load_all(target)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Validation failed:[/red] {e}")
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

    total_tests = sum(len(s.tests) for s in suites)
    console.print(f"[green]✓[/green] {len(suites)} suite(s), {total_tests} test(s) valid")

    for suite in suites:
        console.print(f"  [bold]{suite.suite}[/bold]")
        for test in suite.tests:
            methods_str = test.request.method
            console.print(f"    • {test.name} [{methods_str} {test.request.path}]")


@app.command()
def init(
    output: str = typer.Argument("tests/example.yaml", help="Output file path."),
):
    """Generate a starter test file."""
    template = """\
suite: example-tests
tests:
  - name: health check
    request:
      method: GET
      path: /health
    expect:
      status: 200
      body:
        status: ok
      max_response_time_ms: 1000

  - name: create item
    request:
      method: POST
      path: /items
      headers:
        Content-Type: application/json
      json:
        name: test-item
    expect:
      status: 201
      body:
        id: exists
        name: test-item
    extract:
      item_id: id

  - name: get created item
    request:
      method: GET
      path: /items/${item_id}
    expect:
      status: 200
      body:
        name: test-item
"""
    out_path = Path(output)
    if out_path.exists():
        console.print(f"[red]Error:[/red] File already exists: {output}")
        raise typer.Exit(code=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template, encoding="utf-8")
    console.print(f"[green]✓[/green] Created {output}")
    console.print("  Edit the file, then run:")
    console.print(f"  [bold]api-contract-tester run {output}[/bold]")
