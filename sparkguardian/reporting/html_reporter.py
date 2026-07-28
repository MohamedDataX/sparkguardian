"""Standalone HTML report: single file, inline CSS, dark theme."""
from __future__ import annotations

from sparkguardian.models.report import AnalysisReport
from sparkguardian.scoring.score_engine import ScoreResult

_CSS = """
body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; margin: 0; padding: 2rem; }
h1 { color: #7dd3fc; } h2 { color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: .5rem; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
th { background: #1e293b; color: #7dd3fc; padding: .6rem 1rem; text-align: left; }
td { padding: .5rem 1rem; border-bottom: 1px solid #1e293b; }
tr:hover td { background: #1e293b; }
.CRITICAL { color: #f87171; font-weight: bold; }
.HIGH { color: #fb923c; }
.MEDIUM { color: #fbbf24; }
.LOW { color: #60a5fa; }
.INFO { color: #94a3b8; }
.score { font-size: 2rem; font-weight: bold; }
.score-good { color: #4ade80; }
.score-mid { color: #fbbf24; }
.score-bad { color: #f87171; }
"""


def to_html(report: AnalysisReport, score: ScoreResult | None = None) -> str:
    """Build the report as one self-contained HTML file.

    CSS is inlined so the file can be mailed or attached to a CI job with no
    external assets. Note the fields interpolated below are not HTML-escaped;
    they come from our own rules, not from user input.
    """
    s = report.summary()
    score_html = ""
    if score:
        cls = "score-good" if score.total >= 80 else ("score-mid" if score.total >= 60 else "score-bad")
        score_html = f'<p class="score {cls}">Score: {score.total:.0f}/100</p>'

    rows = ""
    for issue in sorted(report.active_issues, key=lambda i: i.location.line):
        sev = issue.severity.value
        rows += (
            f"<tr><td>{issue.rule_id}</td>"
            f'<td class="{sev}">{sev}</td>'
            f"<td>{issue.impact_type.value}</td>"
            f"<td>{issue.location.line}</td>"
            f"<td>{issue.message}</td>"
            f"<td>{issue.suggestion}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>SparkGuardian — {report.target}</title>
<style>{_CSS}</style></head>
<body>
<h1>SparkGuardian — {report.target}</h1>
<p>Analyzed: {report.analyzed_at.isoformat()} | Duration: {report.duration_ms:.1f}ms</p>
{score_html}
<h2>Summary</h2>
<table><tr><th>Metric</th><th>Count</th></tr>
<tr><td>Total</td><td>{s['total']}</td></tr>
<tr><td>Critical</td><td class="CRITICAL">{s['critical']}</td></tr>
<tr><td>High</td><td class="HIGH">{s['high']}</td></tr>
<tr><td>Medium</td><td class="MEDIUM">{s['medium']}</td></tr>
<tr><td>Low</td><td class="LOW">{s['low']}</td></tr>
<tr><td>Ignored</td><td>{s['ignored']}</td></tr>
</table>
<h2>Issues</h2>
<table>
<tr><th>Rule</th><th>Severity</th><th>Impact</th><th>Line</th><th>Message</th><th>Suggestion</th></tr>
{rows}
</table>
</body></html>"""
