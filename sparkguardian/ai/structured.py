"""Parse LLM answers into typed dataclasses.

Models do not reliably return clean JSON, so parsing never raises: on failure
the raw text is kept in `parse_error` and callers fall back to a heuristic.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class AIAnalysis:
    rule_id: str
    explanation: str
    spark_internals: str
    code_before: str
    code_after: str
    confidence: float
    tags: list[str]
    estimated_impact: str
    raw_response: str = ""
    parse_error: str = ""

    @property
    def is_valid(self) -> bool:
        return not self.parse_error and bool(self.explanation)


@dataclass
class RemediationPlan:
    target: str
    priority_order: list[str]
    effort_estimate: dict[str, str]
    quick_wins: list[str]
    blockers: list[str]
    summary: str
    roi_statement: str
    raw_response: str = ""
    parse_error: str = ""

    @property
    def is_valid(self) -> bool:
        return not self.parse_error


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of a model answer.

    Models wrap JSON in markdown fences, or add a sentence before it. Both are
    handled here rather than in each caller.
    """
    # Fenced block first, it is the common case.
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        return text
    # No fence: brace-count to the matching close, so a nested object does not
    # cut the extraction short.
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def parse_ai_analysis(rule_id: str, raw: str) -> AIAnalysis:
    try:
        data = json.loads(_extract_json(raw))
        return AIAnalysis(
            rule_id=rule_id,
            explanation=data.get("explanation", ""),
            spark_internals=data.get("spark_internals", ""),
            code_before=data.get("code_before", ""),
            code_after=data.get("code_after", ""),
            confidence=float(data.get("confidence", 0.8)),
            tags=data.get("tags", []),
            estimated_impact=data.get("estimated_impact", "MEDIUM"),
            raw_response=raw,
        )
    except Exception as e:
        return AIAnalysis(
            rule_id=rule_id,
            explanation=raw,
            spark_internals="",
            code_before="",
            code_after="",
            confidence=0.5,
            tags=[],
            estimated_impact="MEDIUM",
            raw_response=raw,
            parse_error=str(e),
        )


def parse_remediation_plan(target: str, raw: str) -> RemediationPlan:
    try:
        data = json.loads(_extract_json(raw))
        return RemediationPlan(
            target=target,
            priority_order=data.get("priority_order", []),
            effort_estimate=data.get("effort_estimate", {}),
            quick_wins=data.get("quick_wins", []),
            blockers=data.get("blockers", []),
            summary=data.get("summary", ""),
            roi_statement=data.get("roi_statement", ""),
            raw_response=raw,
        )
    except Exception as e:
        return RemediationPlan(
            target=target,
            priority_order=[],
            effort_estimate={},
            quick_wins=[],
            blockers=[],
            summary=raw,
            roi_statement="",
            raw_response=raw,
            parse_error=str(e),
        )
