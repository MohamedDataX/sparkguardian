"""SparkGuardian CLI — Typer-based."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from sparkguardian import licensing
from sparkguardian.ci.exit_codes import resolve_exit_code
from sparkguardian.config import GuardianConfig
from sparkguardian.constants import APP_NAME, APP_VERSION
from sparkguardian.parser.ast_analyzer import ASTAnalyzer
from sparkguardian.parser.plan_analyzer import PlanAnalyzer
from sparkguardian.reporting.html_reporter import to_html
from sparkguardian.reporting.json_reporter import to_json
from sparkguardian.reporting.markdown_reporter import to_markdown
from sparkguardian.reporting.sarif_reporter import to_sarif
from sparkguardian.reporting.terminal_reporter import print_report
from sparkguardian.rewriter.safe_rewriter import SafeRewriter
from sparkguardian.scoring.score_engine import compute_score
from sparkguardian.utils.file_utils import collect_python_files

# These are only needed for annotations. The real imports stay inside the
# commands so the CLI starts fast without pulling in the AI and cost modules.
if TYPE_CHECKING:
    from sparkguardian.ai.structured import RemediationPlan
    from sparkguardian.cost.estimator import CostEstimate
    from sparkguardian.history.tracker import HistorySnapshot, HistoryStore
    from sparkguardian.models.report import AnalysisReport


# Commands that require a valid license before running.
_GATED_COMMANDS = {"analyze", "fix", "explain-plan", "remediation", "chat", "cost", "history"}

app = typer.Typer(
    name="sparkguardian",
    help=f"{APP_NAME} — PySpark auditing, optimization, and governance framework",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{APP_NAME} v{APP_VERSION}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", callback=_version_callback, is_eager=True),
) -> None:
    # License gate: activates on first run, blocks when expired.
    if ctx.invoked_subcommand in _GATED_COMMANDS:
        try:
            licensing.ensure_licensed(console, prompt=typer.prompt)
        except licensing.LicenseError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc


@app.command()
def activate(
    token: str = typer.Argument(None, help="License token (SG-…). Prompted if omitted."),
) -> None:
    """Activate a SparkGuardian license token (validates online, then caches)."""
    tok = token or typer.prompt("Enter your license token")
    try:
        data = licensing.activate(tok)
    except licensing.LicenseError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print("[green]License activated.[/green]")
    console.print(licensing.status_line(data))


@app.command("license")
def license_status() -> None:
    """Show current license status."""
    console.print(licensing.status_line())


@app.command()
def analyze(
    path: str = typer.Argument(..., help="Python file or directory to analyze"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    output_json: bool = typer.Option(False, "--json", help="Output JSON report"),
    output_html: str | None = typer.Option(None, "--html", help="Write HTML report to file"),
    output_markdown: str | None = typer.Option(None, "--md", help="Write Markdown report to file"),
    output_sarif: str | None = typer.Option(None, "--sarif", help="Write SARIF v2.1.0 report (GitHub Code Scanning)"),
    show_ignored: bool = typer.Option(False, "--show-ignored", help="Show suppressed findings"),
    ai: bool = typer.Option(False, "--ai", help="Enable local AI explanations (requires Ollama)"),
    score: bool = typer.Option(True, "--score/--no-score", help="Show performance score"),
    record_history: bool = typer.Option(False, "--history", help="Record snapshot in audit history"),
) -> None:
    """Analyze PySpark code for anti-patterns."""
    cfg = GuardianConfig.load(config)
    files = collect_python_files(path)

    if not files:
        console.print(f"[red]No Python files found in: {path}[/red]")
        raise typer.Exit(1)

    analyzer = ASTAnalyzer(cfg.rule_configs)
    all_issues = []

    for filepath in files:
        report = analyzer.analyze_file(filepath)
        all_issues.extend(report.issues)


    from sparkguardian.models.report import AnalysisReport
    combined = AnalysisReport(target=path)
    combined.issues = all_issues

    score_result = compute_score(combined) if score else None
    if score_result:
        combined.score = score_result.total
        combined.score_breakdown = score_result.breakdown

    if output_json:
        typer.echo(to_json(combined, score_result))
    else:
        print_report(combined, score_result, show_ignored=show_ignored)

        if ai and combined.active_issues:
            _run_ai_explanations(combined)

    if output_html:
        Path(output_html).write_text(to_html(combined, score_result), encoding="utf-8")
        console.print(f"[green]HTML report written to {output_html}[/green]")

    if output_markdown:
        Path(output_markdown).write_text(to_markdown(combined, score_result), encoding="utf-8")
        console.print(f"[green]Markdown report written to {output_markdown}[/green]")

    if output_sarif:
        Path(output_sarif).write_text(to_sarif(combined), encoding="utf-8")
        console.print(f"[green]SARIF report written to {output_sarif}[/green]")

    if record_history and score_result:
        from sparkguardian.history.tracker import HistoryStore
        store = HistoryStore()
        snap = store.record(combined, score_result.total, git_branch=_git_branch())
        Console(stderr=True).print(
            f"[dim]History snapshot recorded: {snap.timestamp} | score={snap.score}/100[/dim]"
        )

    exit_code = resolve_exit_code(combined, cfg.fail_on_high)
    raise typer.Exit(exit_code)


def _git_branch() -> str:
    import subprocess
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


@app.command()
def fix(
    path: str = typer.Argument(..., help="Python file to fix"),
    config: str | None = typer.Option(None, "--config", "-c"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt before each fix"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview diff without modifying files"),
) -> None:
    """Apply safe auto-fixes to PySpark code."""
    cfg = GuardianConfig.load(config)
    analyzer = ASTAnalyzer(cfg.rule_configs)
    report = analyzer.analyze_file(path)

    fixable = [i for i in report.active_issues if i.autofix_available]
    if not fixable:
        console.print("[green]No auto-fixable issues found.[/green]")
        raise typer.Exit(0)

    console.print(f"[yellow]{len(fixable)} fixable issue(s) found.[/yellow]")

    rewriter = SafeRewriter()
    result = rewriter.rewrite(
        path,
        report.active_issues,
        dry_run=dry_run,
        interactive=interactive,
    )

    if result.changed:
        if dry_run:
            console.print("\n[bold cyan]--- Diff (dry-run) ---[/bold cyan]")
            typer.echo(result.diff)
        else:
            console.print(f"[green]Applied {len(result.applied_rules)} fix(es): {result.applied_rules}[/green]")
    else:
        console.print("[dim]No changes applied.[/dim]")

    if result.skipped_rules:
        console.print(f"[dim]Skipped: {result.skipped_rules}[/dim]")


@app.command("explain-plan")
def explain_plan(
    plan_file: str = typer.Argument(..., help="File containing Spark explain() output"),
    ai: bool = typer.Option(False, "--ai", help="Enable local AI explanation"),
) -> None:
    """Analyze a Spark execution plan file."""
    plan_text = Path(plan_file).read_text(encoding="utf-8")
    analyzer = PlanAnalyzer()
    issues = analyzer.analyze(plan_text, source=plan_file)

    if not issues:
        console.print("[green]No execution plan issues detected.[/green]")
    else:
        for issue in issues:
            color = "red" if issue.severity.value == "CRITICAL" else "yellow"
            console.print(f"[{color}][{issue.rule_id}] {issue.title}[/{color}]")
            console.print(f"  {issue.message}")
            if issue.suggestion:
                console.print(f"  → {issue.suggestion}")
            console.print()

    if ai:
        try:
            from sparkguardian.ai.local_llm import LocalLLM
            llm = LocalLLM()
            console.print("[bold cyan]AI Explanation:[/bold cyan]")
            console.print(llm.explain_plan(plan_text))
        except Exception as e:
            console.print(f"[red]AI unavailable: {e}[/red]")

    has_critical = any(i.severity.value == "CRITICAL" for i in issues)
    raise typer.Exit(1 if has_critical else 0)


@app.command("list-rules")
def list_rules() -> None:
    """List all available rules."""
    from rich.table import Table

    from sparkguardian.rules.registry import RuleRegistry

    t = Table(title="SparkGuardian Rules", show_lines=True)
    t.add_column("Rule ID", style="cyan", width=10)
    t.add_column("Title")
    t.add_column("Severity", width=10)
    t.add_column("Impact", width=12)
    t.add_column("Category", width=12)
    t.add_column("Autofix", width=8)

    for rule_cls in sorted(RuleRegistry.all_rule_classes(), key=lambda r: r.rule_id):
        instance = rule_cls()
        t.add_row(
            instance.rule_id,
            instance.title,
            instance.severity.value,
            instance.impact_type.value,
            instance.category if isinstance(instance.category, str) else instance.category.value,
            "✓" if instance.autofix_available else "",
        )
    console.print(t)


def _run_ai_explanations(report: AnalysisReport) -> None:
    try:
        from sparkguardian.ai.local_llm import LocalLLM
        from sparkguardian.ai.rag import SparkKnowledgeBase
        llm = LocalLLM()
        if not llm.is_available():
            console.print("[yellow]Ollama not running. Start with: ollama serve[/yellow]")
            return
        llm.auto_select_model()
        kb = SparkKnowledgeBase()
        console.print("\n[bold cyan]AI Explanations (local Ollama):[/bold cyan]")
        for issue in report.active_issues[:3]:
            context = kb.query(issue.title + " " + issue.message, rule_id=issue.rule_id)
            console.print(f"\n[bold cyan]{issue.rule_id}[/bold cyan] — {issue.title}")
            for token in llm.stream_explain_issue(issue, rag_context=context):
                console.print(token, end="")
            console.print()
        stats = llm.cache_stats
        console.print(
            f"\n[dim]AI cache: {stats['size']} entries | "
            f"hit rate {stats['hit_rate']} | "
            f"hits {stats['hits']} / misses {stats['misses']}[/dim]"
        )
    except Exception as e:
        console.print(f"[red]AI error: {e}[/red]")


@app.command("ai-status")
def ai_status(
    model: str | None = typer.Option(None, "--model", "-m", help="Ollama model name"),
) -> None:
    """Check local AI (Ollama) availability and list installed models."""
    from sparkguardian.ai.local_llm import OLLAMA_BASE_URL, LocalLLM
    llm = LocalLLM(model=model or "deepseek-coder:6.7b")

    if llm.is_available():
        console.print(f"[green]Ollama running at {OLLAMA_BASE_URL}[/green]")
        models = llm.list_local_models()
        if models:
            console.print("[bold]Installed models:[/bold]")
            for m in models:
                console.print(f"  • {m}")
        else:
            console.print("[yellow]No models installed. Run: ollama pull deepseek-coder:6.7b[/yellow]")
        selected = llm.auto_select_model()
        console.print(f"[cyan]Auto-selected model: {selected}[/cyan]")
    else:
        console.print(f"[red]Ollama not available at {OLLAMA_BASE_URL}[/red]")
        console.print("Install: https://ollama.ai | Start: ollama serve")
        raise typer.Exit(1)


@app.command()
def remediation(
    path: str = typer.Argument(..., help="Python file or directory to analyze"),
    config: str | None = typer.Option(None, "--config", "-c"),
    model: str | None = typer.Option(None, "--model", "-m", help="Ollama model"),
    output_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Generate AI-driven prioritized remediation plan for a file."""
    from sparkguardian.ai.local_llm import LocalLLM
    from sparkguardian.ai.remediation import RemediationPlanner
    from sparkguardian.scoring.score_engine import compute_score

    cfg = GuardianConfig.load(config)
    files = collect_python_files(path)
    if not files:
        console.print(f"[red]No Python files found: {path}[/red]")
        raise typer.Exit(1)

    analyzer = ASTAnalyzer(cfg.rule_configs)
    from sparkguardian.models.report import AnalysisReport
    combined = AnalysisReport(target=path)
    for f in files:
        combined.issues.extend(analyzer.analyze_file(f).issues)

    score_result = compute_score(combined)
    llm = LocalLLM(model=model or "deepseek-coder:6.7b")

    if not llm.is_available():
        Console(stderr=True).print("[yellow]Ollama not running — using heuristic plan[/yellow]")

    planner = RemediationPlanner(llm)
    plan = planner.generate(combined, score_result.total)

    if output_json:
        import json
        typer.echo(json.dumps({
            "target": plan.target,
            "priority_order": plan.priority_order,
            "effort_estimate": plan.effort_estimate,
            "quick_wins": plan.quick_wins,
            "blockers": plan.blockers,
            "summary": plan.summary,
            "roi_statement": plan.roi_statement,
        }, indent=2))
    else:
        _print_remediation_plan(plan, score_result.total)


def _print_remediation_plan(plan: RemediationPlan, score: float) -> None:
    from rich.table import Table

    console.print()
    console.rule("[bold cyan]SparkGuardian — Remediation Plan[/bold cyan]")
    console.print(f"\n[bold]{plan.target}[/bold] | Score: [yellow]{score:.0f}/100[/yellow]")
    console.print(f"\n[italic]{plan.summary}[/italic]")
    if plan.roi_statement:
        console.print(f"[green]{plan.roi_statement}[/green]")

    if plan.blockers:
        console.print(f"\n[bold red]Blockers (fix before production):[/bold red] {', '.join(plan.blockers)}")
    if plan.quick_wins:
        console.print(f"[bold green]Quick wins (< 30 min):[/bold green] {', '.join(plan.quick_wins)}")

    if plan.priority_order:
        t = Table(title="Priority Order", show_lines=True)
        t.add_column("#", width=4)
        t.add_column("Rule ID", width=10)
        t.add_column("Est. Effort")
        for i, rule_id in enumerate(plan.priority_order, 1):
            effort = plan.effort_estimate.get(rule_id, "—")
            t.add_row(str(i), rule_id, effort)
        console.print(t)


@app.command()
def chat(
    path: str = typer.Argument(..., help="Python file to analyze and chat about"),
    config: str | None = typer.Option(None, "--config", "-c"),
    model: str | None = typer.Option(None, "--model", "-m", help="Ollama model"),
) -> None:
    """Interactive AI chat about audit findings for a file."""
    from sparkguardian.ai.local_llm import LocalLLM
    from sparkguardian.scoring.score_engine import compute_score

    cfg = GuardianConfig.load(config)
    analyzer = ASTAnalyzer(cfg.rule_configs)
    report = analyzer.analyze_file(path)
    score_result = compute_score(report)

    llm = LocalLLM(model=model or "deepseek-coder:6.7b")
    if not llm.is_available():
        console.print("[red]Ollama not running. Start with: ollama serve[/red]")
        raise typer.Exit(1)
    llm.auto_select_model()

    print_report(report, score_result)

    session = llm.create_session(report, score_result.total)

    from sparkguardian.ai.rag import SparkKnowledgeBase
    kb = SparkKnowledgeBase()
    all_context = "\n".join(
        kb.query("", rule_id=i.rule_id) for i in report.active_issues[:5] if kb.query("", rule_id=i.rule_id)
    )
    if all_context:
        session.inject_context(all_context)

    console.print(
        "\n[bold cyan]SparkGuardian AI Chat[/bold cyan] "
        "[dim](type 'exit' to quit, 'reset' to clear history)[/dim]"
    )
    console.print("[dim]Ask anything about the findings above...[/dim]\n")

    while True:
        try:
            question = typer.prompt("You")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if question.strip().lower() in ("exit", "quit", "q"):
            break
        if question.strip().lower() == "reset":
            session.reset()
            console.print("[dim]History cleared.[/dim]")
            continue
        if not question.strip():
            continue

        console.print("\n[bold cyan]AI[/bold cyan] ", end="")
        for token in session.ask_stream(question):
            console.print(token, end="", highlight=False)
        console.print(f"\n\n[dim]Turn {session.turn_count} | Cache: {llm.cache_stats['hit_rate']}[/dim]\n")


# ---------------------------------------------------------------------------
# COST ESTIMATION COMMAND
# ---------------------------------------------------------------------------

@app.command()
def cost(
    path: str = typer.Argument(..., help="Python file or directory"),
    config: str | None = typer.Option(None, "--config", "-c"),
    daily_data_tb: float = typer.Option(1.0, "--data-tb", help="Daily data volume (TB)"),
    cluster_nodes: int = typer.Option(10, "--nodes", help="Cluster node count"),
    runs_per_day: int = typer.Option(1, "--runs", help="Pipeline runs per day"),
    cloud: str = typer.Option(
        "aws_emr", "--cloud",
        help="Cloud provider: aws_emr | databricks | gcp_dataproc | azure_synapse",
    ),
    instance_type: str = typer.Option(
        "m6g.xlarge", "--instance", help="Cluster instance type (e.g. m6g.xlarge)"
    ),
    spot: bool = typer.Option(False, "--spot", help="Price cluster as spot/preemptible (-65%)"),
    output_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Estimate monthly/yearly cloud cost waste from PySpark anti-patterns."""
    from sparkguardian.cost.estimator import CostEstimator, WorkloadProfile

    cfg = GuardianConfig.load(config)
    files = collect_python_files(path)
    if not files:
        console.print(f"[red]No Python files in: {path}[/red]")
        raise typer.Exit(1)

    analyzer = ASTAnalyzer(cfg.rule_configs)
    from sparkguardian.models.report import AnalysisReport
    combined = AnalysisReport(target=path)
    for f in files:
        combined.issues.extend(analyzer.analyze_file(f).issues)

    workload = WorkloadProfile(
        daily_data_tb=daily_data_tb,
        cluster_nodes=cluster_nodes,
        runs_per_day=runs_per_day,
        cloud=cloud,
        instance_type=instance_type,
        is_spot=spot,
    )
    estimator = CostEstimator()
    estimate = estimator.estimate(combined, workload)

    if output_json:
        import json as _json
        from dataclasses import asdict as _asdict
        data = {
            "target": estimate.target,
            "workload": _asdict(estimate.workload),
            "total_monthly_usd": estimate.total_monthly_usd,
            "total_yearly_usd": estimate.total_yearly_usd,
            "by_resource": estimate.by_resource,
            "breakdown": [_asdict(b) for b in estimate.breakdown],
        }
        typer.echo(_json.dumps(data, indent=2))
        return

    _print_cost_estimate(estimate)


def _print_cost_estimate(estimate: CostEstimate) -> None:
    from rich.table import Table
    console.print()
    console.rule(f"[bold cyan]Cloud Cost Estimate — {estimate.target}[/bold cyan]")
    w = estimate.workload
    from sparkguardian.cost.pricing_client import CloudPricingFetcher
    price = CloudPricingFetcher.get_instance_price(w.cloud, w.instance_type)
    spot_note = " spot" if w.is_spot else ""
    console.print(
        f"\n[dim]Workload: {w.daily_data_tb} TB/day | {w.cluster_nodes}× {w.instance_type}"
        f"{spot_note} (${price:.3f}/h) | {w.runs_per_day}x/day | cloud={w.cloud}[/dim]"
    )

    color = "red" if estimate.total_monthly_usd > 1000 else (
        "yellow" if estimate.total_monthly_usd > 200 else "green"
    )
    console.print(
        f"\n[bold {color}]💸 Estimated waste: "
        f"${estimate.total_monthly_usd:,.0f}/month  "
        f"(${estimate.total_yearly_usd:,.0f}/year)[/bold {color}]\n"
    )

    if estimate.by_resource:
        console.print("[bold]By cloud resource:[/bold]")
        for resource, amount in sorted(
            estimate.by_resource.items(), key=lambda x: -x[1]
        ):
            console.print(f"  • {resource:10}  ${amount:>8,.0f}/month")
        console.print()

    if estimate.breakdown:
        t = Table(title="Top cost drivers", show_lines=False)
        t.add_column("Rule", style="cyan", width=8)
        t.add_column("Severity", width=10)
        t.add_column("$/month", justify="right", style="bold")
        t.add_column("Occurr.", justify="right")
        t.add_column("Driver")
        for b in estimate.breakdown[:10]:
            t.add_row(
                b.rule_id,
                b.severity,
                f"${b.scaled_cost_usd:,.0f}",
                str(b.occurrences),
                b.description,
            )
        console.print(t)


# ---------------------------------------------------------------------------
# HISTORY COMMAND
# ---------------------------------------------------------------------------

@app.command()
def history(
    target: str | None = typer.Option(None, "--target", help="Filter by file/dir"),
    limit: int = typer.Option(20, "--limit", "-n", help="Show last N snapshots"),
    output_csv: str | None = typer.Option(None, "--csv", help="Export to CSV"),
    clear: bool = typer.Option(False, "--clear", help="Delete all history (destructive)"),
    output_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show audit history — score evolution over time."""
    from sparkguardian.history.tracker import HistoryStore

    store = HistoryStore()

    if clear:
        typer.confirm("Delete all history snapshots?", abort=True)
        store.clear()
        console.print("[yellow]History cleared.[/yellow]")
        return

    snaps = store.snapshots(target=target, limit=limit)

    if output_csv:
        Path(output_csv).write_text(store.to_csv(target=target), encoding="utf-8")
        console.print(f"[green]CSV exported to {output_csv}[/green]")
        return

    if output_json:
        import json as _json
        from dataclasses import asdict as _asdict
        typer.echo(_json.dumps(
            {"summary": store.summary(), "snapshots": [_asdict(s) for s in snaps]},
            indent=2,
        ))
        return

    if not snaps:
        console.print("[yellow]No history snapshots recorded yet.[/yellow]")
        console.print("[dim]Run: sparkguardian analyze <path> --history[/dim]")
        return

    _print_history(store, snaps, target)


def _print_history(
    store: HistoryStore, snaps: list[HistorySnapshot], target: str | None
) -> None:
    from rich.table import Table

    summary = store.summary()
    console.print()
    console.rule("[bold cyan]SparkGuardian — Audit History[/bold cyan]")
    if target:
        console.print(f"[dim]Filter: {target}[/dim]")
    console.print(
        f"\n[bold]Snapshots: {summary['total_snapshots']}[/bold] | "
        f"unique targets: {summary['unique_targets']}\n"
        f"Score range: {summary['min_score']} → {summary['max_score']} "
        f"| avg: {summary['avg_score']} | latest: {summary['latest_score']}"
    )

    delta = store.score_delta(target=target)
    if delta is not None:
        arrow = "↗️" if delta > 0 else ("↘️" if delta < 0 else "→")
        color = "green" if delta > 0 else ("red" if delta < 0 else "dim")
        console.print(f"\n[bold {color}]{arrow} Latest delta: {delta:+.1f}[/bold {color}]")
        if store.regression_detected(target=target):
            console.print("[bold red]⚠️  REGRESSION DETECTED (delta > -5)[/bold red]")

    t = Table(title=f"Last {len(snaps)} snapshots", show_lines=False)
    t.add_column("Timestamp", style="dim")
    t.add_column("Target")
    t.add_column("Score", justify="right", style="bold")
    t.add_column("Total")
    t.add_column("Crit", style="red", justify="right")
    t.add_column("High", style="yellow", justify="right")
    t.add_column("Branch", style="cyan")
    for s in snaps:
        score_color = "green" if s.score >= 80 else ("yellow" if s.score >= 60 else "red")
        t.add_row(
            s.timestamp[:19],
            s.target[-30:],
            f"[{score_color}]{s.score:.0f}/100[/{score_color}]",
            str(s.total_issues),
            str(s.critical),
            str(s.high),
            s.git_branch or "-",
        )
    console.print(t)
