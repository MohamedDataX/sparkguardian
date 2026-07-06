from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ImpactType(str, Enum):
    COST = "COST"
    RELIABILITY = "RELIABILITY"
    CLARITY = "CLARITY"


class IssueStatus(str, Enum):
    ACTIVE = "ACTIVE"
    IGNORED = "IGNORED"
    FIXED = "FIXED"
    SKIPPED = "SKIPPED"


@dataclass
class Location:
    file: str
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


@dataclass
class Issue:
    rule_id: str
    title: str
    category: str
    severity: Severity
    impact_type: ImpactType
    message: str
    location: Location
    suggestion: str = ""
    explanation: str = ""
    confidence: float = 1.0
    status: IssueStatus = IssueStatus.ACTIVE
    ignore_reason: str = ""
    autofix_available: bool = False

    def is_blocking(self) -> bool:
        return self.severity == Severity.CRITICAL

    def __str__(self) -> str:
        return (
            f"[{self.rule_id}] {self.title} @ {self.location} "
            f"({self.severity.value}/{self.impact_type.value})"
        )
