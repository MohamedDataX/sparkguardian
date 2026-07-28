"""Runs the dynamic (plan-level) rules over a Spark execution plan.

This is the runtime counterpart of ASTAnalyzer: the AST side sees the source
code, this side sees what Catalyst actually decided to do with it. Some issues
are only visible here, a missed broadcast for instance, because the decision
depends on table statistics rather than on how the code was written.
"""
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
        # 3 shuffles is where plans in practice start looking suspicious. It is
        # a judgement call, hence the constructor argument.
        self._shuffle_threshold = shuffle_threshold

    def analyze(self, plan_text: str, source: str = "<plan>") -> list[Issue]:
        # Parse once and hand the same node list to every check; the plans we
        # get are small, but re-parsing per rule would be wasteful for nothing.
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
