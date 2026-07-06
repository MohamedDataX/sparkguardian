from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sparkguardian.models.issue import Issue, IssueStatus, Severity


@dataclass
class AnalysisReport:
    target: str
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    issues: list[Issue] = field(default_factory=list)
    score: float | None = None
    score_breakdown: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def active_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.status == IssueStatus.ACTIVE]

    @property
    def ignored_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.status == IssueStatus.IGNORED]

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.active_issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.active_issues if i.severity == Severity.HIGH)

    @property
    def has_blocking_issues(self) -> bool:
        return self.critical_count > 0

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.issues),
            "active": len(self.active_issues),
            "ignored": len(self.ignored_issues),
            "critical": self.critical_count,
            "high": self.high_count,
            "medium": sum(1 for i in self.active_issues if i.severity == Severity.MEDIUM),
            "low": sum(1 for i in self.active_issues if i.severity == Severity.LOW),
        }
