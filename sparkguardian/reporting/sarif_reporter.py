"""SARIF (Static Analysis Results Interchange Format) v2.1.0 reporter.

SARIF is the industry standard format for static analysis tools, supported by:
  - GitHub Code Scanning (Security tab integration)
  - GitLab Code Quality / SAST
  - Azure DevOps
  - Sonarqube
  - VS Code SARIF Viewer extension

Spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
"""
from __future__ import annotations

import json

from sparkguardian.constants import APP_NAME, APP_VERSION
from sparkguardian.models.issue import Severity
from sparkguardian.models.report import AnalysisReport

_SEVERITY_TO_SARIF: dict[Severity, str] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "none",
}

_SEVERITY_TO_SECURITY_LEVEL: dict[Severity, float] = {
    Severity.CRITICAL: 9.5,
    Severity.HIGH: 7.5,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 2.5,
    Severity.INFO: 1.0,
}


def to_sarif(report: AnalysisReport) -> str:
    """Convert AnalysisReport to SARIF v2.1.0 JSON."""
    rule_ids_seen: dict[str, dict] = {}
    results: list[dict] = []

    for issue in report.active_issues:
        rule_ids_seen.setdefault(
            issue.rule_id,
            {
                "id": issue.rule_id,
                "name": issue.rule_id,
                "shortDescription": {"text": issue.title},
                "fullDescription": {"text": issue.explanation or issue.title},
                "helpUri": f"https://github.com/MohamedDataX/sparkguardian/blob/main/sparkguardian/rules/static_rules.py#{issue.rule_id}",
                "properties": {
                    "category": str(issue.category),
                    "impact": issue.impact_type.value,
                    "security-severity": str(_SEVERITY_TO_SECURITY_LEVEL[issue.severity]),
                    "tags": [issue.impact_type.value.lower()],
                },
                "defaultConfiguration": {
                    "level": _SEVERITY_TO_SARIF[issue.severity],
                },
            },
        )

        results.append(
            {
                "ruleId": issue.rule_id,
                "level": _SEVERITY_TO_SARIF[issue.severity],
                "message": {"text": issue.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": issue.location.file,
                                "uriBaseId": "%SRCROOT%",
                            },
                            "region": {
                                "startLine": max(1, issue.location.line),
                                "startColumn": max(1, issue.location.column + 1),
                                **(
                                    {"endLine": issue.location.end_line}
                                    if issue.location.end_line
                                    else {}
                                ),
                            },
                        }
                    }
                ],
                "properties": {
                    "suggestion": issue.suggestion,
                    "autofix_available": issue.autofix_available,
                    "confidence": issue.confidence,
                },
            }
        )

    sarif = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": APP_NAME,
                        "version": APP_VERSION,
                        "informationUri": "https://github.com/MohamedDataX/sparkguardian",
                        "rules": list(rule_ids_seen.values()),
                    }
                },
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": report.analyzed_at.isoformat(),
                    }
                ],
                "properties": {
                    "score": report.score,
                    "duration_ms": report.duration_ms,
                    "total_issues": len(report.issues),
                    "active_issues": len(report.active_issues),
                },
            }
        ],
    }

    return json.dumps(sarif, indent=2, ensure_ascii=False)
