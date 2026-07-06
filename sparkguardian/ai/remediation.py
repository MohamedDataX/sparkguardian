"""RemediationPlanner — AI-driven prioritized action plan from AnalysisReport."""
from __future__ import annotations

from sparkguardian.ai.prompts import REMEDIATION_PLAN_PROMPT
from sparkguardian.ai.structured import RemediationPlan, parse_remediation_plan
from sparkguardian.models.issue import Severity
from sparkguardian.models.report import AnalysisReport
from sparkguardian.utils.logger import get_logger

logger = get_logger(__name__)

_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


class RemediationPlanner:
    def __init__(self, llm: object) -> None:
        self._llm = llm  # LocalLLM instance

    def generate(self, report: AnalysisReport, score: float) -> RemediationPlan:
        if not report.active_issues:
            return RemediationPlan(
                target=report.target,
                priority_order=[],
                effort_estimate={},
                quick_wins=[],
                blockers=[],
                summary="No active issues found.",
                roi_statement="Code is already optimized.",
            )

        issues_text = self._format_issues(report)
        prompt = REMEDIATION_PLAN_PROMPT.format(
            target=report.target,
            score=f"{score:.0f}",
            total=len(report.active_issues),
            issues_text=issues_text,
        )
        raw = self._llm._chat(prompt)
        plan = parse_remediation_plan(report.target, raw)

        if plan.parse_error:
            logger.warning("Remediation parse failed, using heuristic fallback")
            plan = self._heuristic_plan(report, score)

        return plan

    # ------------------------------------------------------------------

    def _format_issues(self, report: AnalysisReport) -> str:
        sorted_issues = sorted(
            report.active_issues,
            key=lambda i: _SEVERITY_RANK.get(i.severity, 4),
        )
        lines = []
        for issue in sorted_issues[:15]:
            lines.append(
                f"  [{issue.rule_id}] {issue.severity.value} | {issue.impact_type.value} "
                f"| line {issue.location.line}: {issue.message}"
            )
        return "\n".join(lines)

    def _heuristic_plan(self, report: AnalysisReport, score: float) -> RemediationPlan:
        """Deterministic fallback when LLM unavailable or parse fails."""
        sorted_issues = sorted(
            report.active_issues,
            key=lambda i: _SEVERITY_RANK.get(i.severity, 4),
        )
        priority = [i.rule_id for i in sorted_issues]
        blockers = [i.rule_id for i in sorted_issues if i.severity == Severity.CRITICAL]
        quick_wins = [i.rule_id for i in sorted_issues if i.autofix_available]

        effort: dict[str, str] = {}
        for issue in sorted_issues:
            if issue.autofix_available:
                effort[issue.rule_id] = "< 5 min (autofix available)"
            elif issue.severity in (Severity.LOW, Severity.INFO):
                effort[issue.rule_id] = "< 30 min"
            elif issue.severity == Severity.MEDIUM:
                effort[issue.rule_id] = "1-2 hours"
            else:
                effort[issue.rule_id] = "2-4 hours"

        return RemediationPlan(
            target=report.target,
            priority_order=priority,
            effort_estimate=effort,
            quick_wins=quick_wins,
            blockers=blockers,
            summary=(
                f"Found {len(report.active_issues)} issues (score {score:.0f}/100). "
                f"{len(blockers)} blocker(s) must be fixed before production."
            ),
            roi_statement=(
                "Fixing HIGH+ issues estimated to reduce shuffle cost and driver OOM risk significantly."
            ),
        )
