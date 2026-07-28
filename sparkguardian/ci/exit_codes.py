"""Translate a report into a process exit code for CI."""
from sparkguardian.constants import EXIT_CRITICAL, EXIT_SUCCESS, EXIT_WARNINGS
from sparkguardian.models.report import AnalysisReport


def resolve_exit_code(report: AnalysisReport, fail_on_high: bool = False) -> int:
    """0 clean, 1 findings, 2 blocking. Only 2 should fail a build."""
    if report.has_blocking_issues:
        return EXIT_CRITICAL
    if fail_on_high and report.high_count > 0:
        return EXIT_CRITICAL
    if len(report.active_issues) > 0:
        return EXIT_WARNINGS
    return EXIT_SUCCESS
