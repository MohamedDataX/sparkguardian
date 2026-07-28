"""Rich terminal reporter."""
from __future__ import annotations

from collections import defaultdict

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from sparkguardian.models.issue import Issue
from sparkguardian.models.report import AnalysisReport
from sparkguardian.rules.severity import SEVERITY_COLORS, SEVERITY_ICONS
from sparkguardian.scoring.score_engine import ScoreResult

console = Console()


def print_report(report: AnalysisReport, score: ScoreResult | None = None, show_ignored: bool = False) -> None:
    console.print()
    console.rule(f"[bold cyan]SparkGuardian — {report.target}[/bold cyan]")

    active = report.active_issues
    if not active:
        console.print("[bold green]✓ No issues found.[/bold green]")
    else:
        by_file: dict[str, list[Issue]] = defaultdict(list)
        for issue in active:
            by_file[issue.location.file].append(issue)

        for filepath, issues in by_file.items():
            console.print(f"\n[bold]{filepath}[/bold]")
            t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
            t.add_column("Line", style="dim", width=6)
            t.add_column("Rule", width=8)
            t.add_column("Severity", width=10)
            t.add_column("Impact", width=12)
            t.add_column("Message")
            for issue in sorted(issues, key=lambda i: i.location.line):
                color = SEVERITY_COLORS.get(issue.severity, "white")
                icon = SEVERITY_ICONS.get(issue.severity, "")
                t.add_row(
                    str(issue.location.line),
                    issue.rule_id,
                    Text(f"{icon} {issue.severity.value}", style=color),
                    issue.impact_type.value,
                    issue.message,
                )
            console.print(t)

            for issue in sorted(issues, key=lambda i: i.location.line):
                if issue.suggestion:
                    console.print(
                        f"  [dim]{issue.rule_id}[/dim] → [italic]{issue.suggestion}[/italic]"
                    )

    if show_ignored and report.ignored_issues:
        console.print(f"\n[dim]Ignored: {len(report.ignored_issues)} finding(s)[/dim]")
        for issue in report.ignored_issues:
            console.print(f"  [dim]{issue.rule_id} @ line {issue.location.line} — {issue.ignore_reason}[/dim]")

    _print_summary(report, score)


def _print_summary(report: AnalysisReport, score: ScoreResult | None) -> None:
    s = report.summary()
    console.print()
    grid = Table.grid(padding=(0, 2))
    grid.add_row(
        f"[bold]Total:[/bold] {s['total']}",
        f"[red]Critical: {s['critical']}[/red]",
        f"[yellow]High: {s['high']}[/yellow]",
        f"[blue]Medium: {s['medium']}[/blue]",
        f"[dim]Low: {s['low']}[/dim]",
        f"[dim]Ignored: {s['ignored']}[/dim]",
    )
    console.print(grid)
    if score:
        color = "green" if score.total >= 80 else ("yellow" if score.total >= 60 else "red")
        console.print(f"\n[bold {color}]Spark Performance Score: {score.total:.0f}/100[/bold {color}]")
    console.print(f"[dim]Analyzed in {report.duration_ms:.1f}ms[/dim]")
    console.print()
