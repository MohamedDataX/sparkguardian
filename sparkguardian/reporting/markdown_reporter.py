"""Markdown report, meant for CI job summaries and pull request comments."""
from __future__ import annotations

from sparkguardian.models.issue import IssueStatus
from sparkguardian.models.report import AnalysisReport
from sparkguardian.rules.severity import SEVERITY_ICONS
from sparkguardian.scoring.score_engine import ScoreResult


def to_markdown(report: AnalysisReport, score: ScoreResult | None = None) -> str:
    lines = [
        f"# SparkGuardian Report — `{report.target}`",
        f"\nAnalyzed at: {report.analyzed_at.isoformat()}  ",
        f"Duration: {report.duration_ms:.1f}ms\n",
    ]

    if score:
        lines.append(f"## Score: {score.total:.0f}/100\n")

    s = report.summary()
    lines += [
        "## Summary\n",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total | {s['total']} |",
        f"| Critical | {s['critical']} |",
        f"| High | {s['high']} |",
        f"| Medium | {s['medium']} |",
        f"| Low | {s['low']} |",
        f"| Ignored | {s['ignored']} |",
        "",
    ]

    active = [i for i in report.issues if i.status == IssueStatus.ACTIVE]
    if active:
        lines += [
            "## Issues\n",
            "| Rule | Severity | Impact | Line | Message |",
            "|------|----------|--------|------|---------|",
        ]
        for issue in sorted(active, key=lambda i: (i.severity.value, i.location.line)):
            icon = SEVERITY_ICONS.get(issue.severity, "")
            lines.append(
                f"| {issue.rule_id} | {icon} {issue.severity.value} | "
                f"{issue.impact_type.value} | {issue.location.line} | {issue.message} |"
            )
        lines.append("")

    ignored = [i for i in report.issues if i.status == IssueStatus.IGNORED]
    if ignored:
        lines.append("## Ignored Findings\n")
        for issue in ignored:
            lines.append(f"- `{issue.rule_id}` line {issue.location.line} — {issue.ignore_reason}")
        lines.append("")

    return "\n".join(lines)
