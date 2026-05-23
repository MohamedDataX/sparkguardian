"""Spark optimization score: 0-100."""
from __future__ import annotations

from dataclasses import dataclass

from sparkguardian.models.issue import Severity
from sparkguardian.models.report import AnalysisReport


@dataclass
class ScoreResult:
    total: float
    breakdown: dict[str, float]

    def __str__(self) -> str:
        return f"Spark Performance Score: {self.total:.0f}/100"


_SEVERITY_PENALTY: dict[Severity, float] = {
    Severity.CRITICAL: 20.0,
    Severity.HIGH: 10.0,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 2.0,
    Severity.INFO: 0.5,
}


def compute_score(report: AnalysisReport) -> ScoreResult:
    score = 100.0
    breakdown: dict[str, float] = {
        "reliability": 0.0,
        "cost": 0.0,
        "clarity": 0.0,
    }

    for issue in report.active_issues:
        penalty = _SEVERITY_PENALTY.get(issue.severity, 2.0)
        score -= penalty
        dim = issue.impact_type.value.lower()
        breakdown[dim] = breakdown.get(dim, 0.0) + penalty

    score = max(0.0, min(100.0, score))
    return ScoreResult(total=round(score, 1), breakdown=breakdown)
