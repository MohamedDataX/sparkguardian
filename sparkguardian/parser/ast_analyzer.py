"""Static analysis entry point: parse a file, run every rule, return a report.

Nothing here executes the code being analyzed. That is the whole point of the
static side: you can point SparkGuardian at a pipeline in CI without a Spark
session, without credentials, and without the risk of running someone's job.

libcst is used rather than the stdlib ``ast`` because it keeps comments and
formatting in the tree. The rewriter needs that to produce readable patches, and
sharing one parse between analysis and rewriting keeps the two consistent.
"""
from __future__ import annotations

import time
from pathlib import Path

import libcst as cst

import sparkguardian.rules.static_rules  # noqa: F401 — registers rules via decorators
from sparkguardian.models.issue import Issue
from sparkguardian.models.report import AnalysisReport
from sparkguardian.parser.ignore_handler import apply_ignores, parse_ignore_directives
from sparkguardian.rules.base import RuleConfig
from sparkguardian.rules.registry import RuleRegistry
from sparkguardian.utils.logger import get_logger

logger = get_logger(__name__)


class ASTAnalyzer:
    def __init__(self, rule_configs: dict[str, RuleConfig] | None = None) -> None:
        # Rules are instantiated once and reused for every file. They hold no
        # per-file state, so this saves rebuilding ~20 objects per file.
        self._rules = RuleRegistry.build_rules(rule_configs)

    def analyze_file(self, filepath: str) -> AnalysisReport:
        path = Path(filepath)
        source = path.read_text(encoding="utf-8")
        return self.analyze_source(source, filepath)

    def analyze_source(self, source: str, filepath: str = "<string>") -> AnalysisReport:
        start = time.monotonic()
        report = AnalysisReport(target=filepath)

        try:
            tree = cst.parse_module(source)
        except cst.ParserSyntaxError as e:
            # A file that does not parse is not our problem to report on: return
            # an empty report so a single broken file cannot fail a whole scan.
            logger.error("Parse error in %s: %s", filepath, e)
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        issues: list[Issue] = []
        for rule in self._rules:
            try:
                found = rule.check(tree, filepath)
                issues.extend(found)
            except Exception as e:
                # One rule blowing up on an unusual construct should not cost us
                # the findings of the other twenty. Log it and keep going.
                logger.warning("Rule %s failed on %s: %s", rule.rule_id, filepath, e)

        directives = parse_ignore_directives(source)
        issues = apply_ignores(issues, directives)

        issues = _deduplicate(issues)

        report.issues = issues
        report.duration_ms = (time.monotonic() - start) * 1000
        return report


def _deduplicate(issues: list[Issue]) -> list[Issue]:
    """Drop repeated findings, keeping the first of each.

    Two rules can flag the same expression (a ``.collect()`` in a loop trips
    both CY001 and CY004), and a single rule visiting nested nodes can report
    the same position twice. Position plus rule id is enough to tell them apart.
    """
    seen: set[tuple[str, str, int, int]] = set()
    result: list[Issue] = []
    for issue in issues:
        key = (issue.rule_id, issue.location.file, issue.location.line, issue.location.column)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
