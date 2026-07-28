from __future__ import annotations

import json
from typing import Any

from sparkguardian.models.report import AnalysisReport
from sparkguardian.scoring.score_engine import ScoreResult


def to_json(report: AnalysisReport, score: ScoreResult | None = None, indent: int = 2) -> str:
    data: dict[str, Any] = {
        "target": report.target,
        "analyzed_at": report.analyzed_at.isoformat(),
        "duration_ms": report.duration_ms,
        "summary": report.summary(),
        "score": score.total if score else None,
        "score_breakdown": score.breakdown if score else {},
        "issues": [
            {
                "rule_id": i.rule_id,
                "title": i.title,
                "category": i.category if isinstance(i.category, str) else i.category.value,
                "severity": i.severity.value,
                "impact_type": i.impact_type.value,
                "status": i.status.value,
                "message": i.message,
                "suggestion": i.suggestion,
                "location": {
                    "file": i.location.file,
                    "line": i.location.line,
                    "column": i.location.column,
                },
                "confidence": i.confidence,
                "autofix_available": i.autofix_available,
            }
            for i in report.issues
        ],
    }
    return json.dumps(data, indent=indent, ensure_ascii=False)
