"""Base class every rule inherits, plus its per-project config."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import libcst as cst

from sparkguardian.models.issue import ImpactType, Issue, Location, Severity


@dataclass
class RuleConfig:
    enabled: bool = True
    severity: Severity | None = None
    threshold: float | None = None
    extra: dict[str, str] = field(default_factory=dict)


class BaseRule(ABC):
    rule_id: str
    title: str
    category: str
    severity: Severity
    impact_type: ImpactType
    explanation: str = ""
    suggestion: str = ""
    autofix_available: bool = False

    def __init__(self, config: RuleConfig | None = None) -> None:
        self._config = config or RuleConfig()
        # A project can raise or lower a rule's severity without editing it.
        if self._config.severity:
            self.severity = self._config.severity

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @abstractmethod
    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        ...

    # Rules only supply the position and a message; everything else comes
    # from the class attributes above, so wording stays consistent.
    def _make_issue(
        self,
        filepath: str,
        line: int,
        column: int,
        message: str,
        end_line: int | None = None,
        end_column: int | None = None,
    ) -> Issue:
        return Issue(
            rule_id=self.rule_id,
            title=self.title,
            category=self.category,
            severity=self.severity,
            impact_type=self.impact_type,
            message=message,
            location=Location(
                file=filepath,
                line=line,
                column=column,
                end_line=end_line,
                end_column=end_column,
            ),
            suggestion=self.suggestion,
            explanation=self.explanation,
            autofix_available=self.autofix_available,
        )
