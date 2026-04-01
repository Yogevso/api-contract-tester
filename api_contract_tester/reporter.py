"""Terminal reporter for test results with multiple output formats."""

from __future__ import annotations

import json
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from api_contract_tester.assertions import TestResult

console = Console()


def print_result(
    result: TestResult,
    verbose: bool = False,
    request_info: dict[str, Any] | None = None,
) -> None:
    """Print a single test result."""
    if result.passed:
        status = Text(" PASS ", style="bold white on green")
    else:
        status = Text(" FAIL ", style="bold white on red")

    console.print(status, result.test_name, f"({result.elapsed_ms:.0f}ms)")

    if result.error:
        console.print(f"       Error: {result.error}", style="red")

    if verbose and request_info:
        console.print(
            f"       {request_info.get('method', '?')} {request_info.get('url', '?')}",
            style="dim",
        )
        if request_info.get("status_code"):
            console.print(f"       Response: {request_info['status_code']}", style="dim")

    if not result.passed or verbose:
        for a in result.assertions:
            if a.passed:
                icon = "[green]  ✓[/green]"
            else:
                icon = "[red]  ✗[/red]"
            console.print(f"     {icon} {a.message}")


def print_summary(results: list[TestResult], total_time_ms: float) -> None:
    """Print the final summary as a Rich table."""
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    console.print()

    # Results table
    table = Table(title="Test Results", show_lines=False, padding=(0, 1))
    table.add_column("Status", justify="center", width=6)
    table.add_column("Test", min_width=30)
    table.add_column("Time", justify="right", width=10)

    for r in results:
        if r.passed:
            status_text = Text("PASS", style="bold green")
        else:
            status_text = Text("FAIL", style="bold red")
        table.add_row(status_text, r.test_name, f"{r.elapsed_ms:.0f}ms")

    console.print(table)
    console.print()

    # Colored icon summary line
    console.print(f"  [green]✔ {passed} passed[/green]")
    if failed:
        console.print(f"  [red]✖ {failed} failed[/red]")
    console.print(f"  [cyan]⏱ {total_time_ms / 1000:.2f}s[/cyan]")
    console.print()

    # Summary panel
    if failed == 0:
        summary_text = (
            f"[bold green]All {passed} tests passed[/bold green]  ({total_time_ms:.0f}ms)"
        )
        console.print(Panel(summary_text, title="Summary", border_style="green"))
    else:
        summary_text = (
            f"[bold green]{passed} passed[/bold green]  "
            f"[bold red]{failed} failed[/bold red]  "
            f"({total_time_ms:.0f}ms)"
        )
        console.print(Panel(summary_text, title="Summary", border_style="red"))
        console.print()
        console.print("  [red]Failed tests:[/red]")
        for r in results:
            if not r.passed:
                console.print(f"    • {r.test_name}")
                if r.error:
                    console.print(f"      {r.error}", style="dim red")
                for a in r.assertions:
                    if not a.passed:
                        console.print(f"      {a.message}", style="dim red")

    console.print()


def should_exit_failure(results: list[TestResult]) -> bool:
    return any(not r.passed for r in results)


# --- JSON Report ---


def generate_json_report(results: list[TestResult], total_time_ms: float) -> str:
    """Generate a JSON report string."""
    passed = sum(1 for r in results if r.passed)
    report = {
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "time_ms": round(total_time_ms, 1),
        },
        "tests": [
            {
                "name": r.test_name,
                "suite": r.suite_name,
                "passed": r.passed,
                "time_ms": round(r.elapsed_ms, 1),
                "error": r.error,
                "assertions": [
                    {"passed": a.passed, "message": a.message} for a in r.assertions
                ],
            }
            for r in results
        ],
    }
    return json.dumps(report, indent=2)


# --- JUnit XML Report ---


def generate_junit_report(results: list[TestResult], total_time_ms: float) -> str:
    """Generate a JUnit-compatible XML report string."""
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    testsuites = Element("testsuites")
    testsuite = SubElement(
        testsuites,
        "testsuite",
        name="api-contract-tester",
        tests=str(len(results)),
        failures=str(failed),
        time=f"{total_time_ms / 1000:.3f}",
    )

    for r in results:
        testcase = SubElement(
            testsuite,
            "testcase",
            name=r.test_name,
            classname=r.suite_name or "default",
            time=f"{r.elapsed_ms / 1000:.3f}",
        )
        if not r.passed:
            failure_messages = []
            if r.error:
                failure_messages.append(r.error)
            for a in r.assertions:
                if not a.passed:
                    failure_messages.append(a.message)
            failure = SubElement(testcase, "failure", message="Test failed")
            failure.text = "\n".join(failure_messages)

    return tostring(testsuites, encoding="unicode", xml_declaration=True)


# --- Diff Report ---


def print_diff_result(diff: "ResponseDiff") -> None:  # noqa: F821 (forward ref)
    """Print a single diff comparison result."""

    if diff.identical:
        status = Text(" SAME ", style="bold white on green")
        console.print(status, diff.test_name)
        return

    status = Text(" DIFF ", style="bold white on yellow")
    console.print(status, diff.test_name)

    if diff.left_error or diff.right_error:
        if diff.left_error:
            console.print(f"     [red]← error: {diff.left_error}[/red]")
        if diff.right_error:
            console.print(f"     [red]→ error: {diff.right_error}[/red]")
        return

    if not diff.status_match:
        console.print(f"     [yellow]status:[/yellow] {diff.left_status} → {diff.right_status}")

    for fd in diff.body_diffs:
        console.print(f"     [yellow]{fd.path}:[/yellow] {fd.left!r} → {fd.right!r}")

    for fd in diff.header_diffs:
        console.print(f"     [dim yellow]header {fd.path}:[/dim yellow] {fd.left!r} → {fd.right!r}")


def print_diff_summary(diffs: list, total_time_ms: float) -> None:
    """Print summary for a diff run."""
    identical = sum(1 for d in diffs if d.identical)
    changed = len(diffs) - identical

    console.print()
    console.print(f"  [green]✔ {identical} identical[/green]")
    if changed:
        console.print(f"  [yellow]✖ {changed} different[/yellow]")
    console.print(f"  [cyan]⏱ {total_time_ms / 1000:.2f}s[/cyan]")
    console.print()

    if changed == 0:
        console.print(Panel(
            f"[bold green]All {identical} responses identical[/bold green]",
            title="Diff Summary", border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold green]{identical} identical[/bold green]  "
            f"[bold yellow]{changed} different[/bold yellow]",
            title="Diff Summary", border_style="yellow",
        ))


# --- Snapshot Report ---


def print_snapshot_result(result: "SnapshotResult") -> None:  # noqa: F821
    """Print a single snapshot comparison result."""
    if result.snapshot_missing:
        status = Text(" NEW  ", style="bold white on blue")
        console.print(status, result.test_name)
        return

    if result.matched:
        status = Text(" SAME ", style="bold white on green")
        console.print(status, result.test_name)
        return

    status = Text(" DIFF ", style="bold white on yellow")
    console.print(status, result.test_name)
    for m in result.mismatches:
        console.print(f"     [yellow]{m.path}:[/yellow] {m.expected!r} → {m.actual!r}")


def print_snapshot_summary(results: list, total_time_ms: float) -> None:
    """Print summary for a snapshot comparison run."""
    matched = sum(1 for r in results if r.matched)
    new = sum(1 for r in results if r.snapshot_missing)
    changed = len(results) - matched - new

    console.print()
    console.print(f"  [green]✔ {matched} matched[/green]")
    if new:
        console.print(f"  [blue]● {new} new (no snapshot)[/blue]")
    if changed:
        console.print(f"  [yellow]✖ {changed} changed[/yellow]")
    console.print(f"  [cyan]⏱ {total_time_ms / 1000:.2f}s[/cyan]")
    console.print()
