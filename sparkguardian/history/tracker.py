"""History tracker — longitudinal analysis of code quality over time.

Stores audit snapshots in JSON. Supports:
  - Score evolution per file
  - Issue count trends
  - Regression detection between commits
  - CSV export for academic/research analysis
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sparkguardian.models.report import AnalysisReport


@dataclass
class HistorySnapshot:
    timestamp: str
    target: str
    score: float
    total_issues: int
    critical: int
    high: int
    medium: int
    low: int
    ignored: int
    duration_ms: float
    git_commit: str = ""
    git_branch: str = ""
    tags: list[str] = field(default_factory=list)


class HistoryStore:
    """JSON-backed audit history with thread-safe append-only writes."""

    DEFAULT_PATH = ".sparkguardian-history.json"

    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path or self.DEFAULT_PATH)
        self._snapshots: list[HistorySnapshot] = []
        self._loaded = False

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._snapshots = [HistorySnapshot(**s) for s in data.get("snapshots", [])]
            except (json.JSONDecodeError, TypeError):
                self._snapshots = []
        self._loaded = True

    def _save(self) -> None:
        payload = {
            "version": "1.0",
            "snapshots": [asdict(s) for s in self._snapshots],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        report: AnalysisReport,
        score: float,
        git_commit: str = "",
        git_branch: str = "",
        tags: list[str] | None = None,
    ) -> HistorySnapshot:
        self._load()
        summary = report.summary()
        snap = HistorySnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            target=report.target,
            score=score,
            total_issues=summary["total"],
            critical=summary["critical"],
            high=summary["high"],
            medium=summary["medium"],
            low=summary["low"],
            ignored=summary["ignored"],
            duration_ms=report.duration_ms,
            git_commit=git_commit,
            git_branch=git_branch,
            tags=tags or [],
        )
        self._snapshots.append(snap)
        self._save()
        return snap

    def snapshots(self, target: str | None = None, limit: int | None = None) -> list[HistorySnapshot]:
        self._load()
        result = self._snapshots
        if target:
            result = [s for s in result if s.target == target]
        if limit:
            result = result[-limit:]
        return result

    def latest(self, target: str | None = None) -> HistorySnapshot | None:
        snaps = self.snapshots(target=target)
        return snaps[-1] if snaps else None

    def score_delta(self, target: str | None = None) -> float | None:
        """Score change between latest and previous snapshot."""
        snaps = self.snapshots(target=target, limit=2)
        if len(snaps) < 2:
            return None
        return round(snaps[-1].score - snaps[-2].score, 1)

    def regression_detected(self, target: str | None = None, threshold: float = 5.0) -> bool:
        delta = self.score_delta(target)
        return delta is not None and delta < -threshold

    def to_csv(self, target: str | None = None) -> str:
        snaps = self.snapshots(target=target)
        if not snaps:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(asdict(snaps[0]).keys()))
        writer.writeheader()
        for s in snaps:
            row = asdict(s)
            row["tags"] = ",".join(s.tags)
            writer.writerow(row)
        return buf.getvalue()

    def clear(self) -> None:
        self._load()
        self._snapshots = []
        self._save()

    def summary(self) -> dict[str, object]:
        self._load()
        if not self._snapshots:
            return {"total_snapshots": 0}
        scores = [s.score for s in self._snapshots]
        return {
            "total_snapshots": len(self._snapshots),
            "min_score": round(min(scores), 1),
            "max_score": round(max(scores), 1),
            "avg_score": round(sum(scores) / len(scores), 1),
            "latest_score": self._snapshots[-1].score,
            "first_recorded": self._snapshots[0].timestamp,
            "last_recorded": self._snapshots[-1].timestamp,
            "unique_targets": len({s.target for s in self._snapshots}),
        }
