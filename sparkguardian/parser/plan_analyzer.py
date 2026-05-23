"""Execution plan analyzer — wraps parser + dynamic rules."""
from __future__ import annotations

from sparkguardian.models.issue import Issue
from sparkguardian.parser.execution_parser import ExecutionPlanParser
from sparkguardian.rules.dynamic_rules import (
    check_adaptive_disabled,
    check_cartesian_product,
    check_excessive_shuffles,
    check_missing_broadcast,
    check_window_without_partition,
)


class PlanAnalyzer:
    def __init__(self, shuffle_threshold: int = 3) -> None:
        self._parser = ExecutionPlanParser()
        self._shuffle_threshold = shuffle_threshold

    def analyze(self, plan_text: str, source: str = "<plan>") -> list[Issue]:
        nodes = self._parser.parse(plan_text)
        issues: list[Issue] = []
        issues.extend(check_cartesian_product(nodes, source))
        issues.extend(check_excessive_shuffles(nodes, source, self._shuffle_threshold))
        issues.extend(check_missing_broadcast(nodes, source))
        issues.extend(check_window_without_partition(nodes, source))
        issues.extend(check_adaptive_disabled(nodes, source))
        return issues

    def shuffle_count(self, plan_text: str) -> int:
        nodes = self._parser.parse(plan_text)
        return self._parser.shuffle_count(nodes)
