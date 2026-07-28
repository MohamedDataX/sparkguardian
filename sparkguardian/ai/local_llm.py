"""Local-only LLM client via Ollama. No cloud inference. No source code exfiltration."""
from __future__ import annotations

import json
from collections.abc import Iterator

from sparkguardian.ai.cache import AIResponseCache
from sparkguardian.ai.prompts import (
    CHAT_SYSTEM_PROMPT,
    EXPLAIN_FINDING_PROMPT,
    EXPLAIN_PLAN_PROMPT,
    STRUCTURED_ANALYSIS_PROMPT,
    SUGGEST_REFACTOR_PROMPT,
    SYSTEM_PROMPT,
)
from sparkguardian.ai.structured import AIAnalysis, parse_ai_analysis
from sparkguardian.models.issue import Issue
from sparkguardian.models.report import AnalysisReport
from sparkguardian.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "deepseek-coder:6.7b"
FALLBACK_MODELS = ["deepseek-coder:6.7b", "codellama:7b", "llama3:8b", "mistral:7b"]
OLLAMA_BASE_URL = "http://localhost:11434"


class LocalLLM:
    """
    Local LLM client with:
    - in-process response cache (LRU)
    - system prompt injection (role anchor)
    - structured JSON output parsing
    - streaming support
    - health check + model auto-select
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = 120,
        cache_size: int = 128,
        use_system_prompt: bool = True,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._cache = AIResponseCache(max_size=cache_size)
        self._system_prompt = SYSTEM_PROMPT if use_system_prompt else ""

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            import httpx  # type: ignore[import]
            r = httpx.get(f"{self._base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def list_local_models(self) -> list[str]:
        try:
            import httpx  # type: ignore[import]
            r = httpx.get(f"{self._base_url}/api/tags", timeout=3)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def auto_select_model(self) -> str:
        available = self.list_local_models()
        for candidate in FALLBACK_MODELS:
            if any(candidate in m for m in available):
                self._model = candidate
                return candidate
        return self._model

    @property
    def cache_stats(self) -> dict[str, object]:
        return self._cache.stats()

    # ------------------------------------------------------------------
    # Public API — plain text
    # ------------------------------------------------------------------

    def explain_issue(self, issue: Issue, rag_context: str = "") -> str:
        prompt = EXPLAIN_FINDING_PROMPT.format(
            rule_id=issue.rule_id,
            title=issue.title,
            severity=issue.severity.value,
            message=issue.message,
            suggestion=issue.suggestion,
            context=f"\nAdditional context:\n{rag_context}" if rag_context else "",
        )
        return self._chat(prompt)

    def explain_plan(self, plan_text: str) -> str:
        prompt = EXPLAIN_PLAN_PROMPT.format(plan_text=plan_text)
        return self._chat(prompt)

    def suggest_refactor(self, code_snippet: str, rule_id: str, suggestion: str) -> str:
        prompt = SUGGEST_REFACTOR_PROMPT.format(
            code=code_snippet,
            rule_id=rule_id,
            suggestion=suggestion,
        )
        return self._chat(prompt)

    def explain_report_summary(self, report: AnalysisReport) -> str:
        s = report.summary()
        issues_text = "\n".join(
            f"- [{i.rule_id}] {i.title} (line {i.location.line}): {i.message}"
            for i in report.active_issues[:10]
        )
        prompt = (
            f"A SparkGuardian audit found {s['total']} issues in '{report.target}':\n"
            f"{issues_text}\n\n"
            "Summarize the top 3 performance risks and prioritize what to fix first. "
            "Be concise and actionable."
        )
        return self._chat(prompt)

    # ------------------------------------------------------------------
    # Public API — structured output
    # ------------------------------------------------------------------

    def analyze_issue_structured(self, issue: Issue, rag_context: str = "") -> AIAnalysis:
        """Return structured AIAnalysis with parsed code_before/after, confidence, tags."""
        prompt = STRUCTURED_ANALYSIS_PROMPT.format(
            rule_id=issue.rule_id,
            title=issue.title,
            severity=issue.severity.value,
            message=issue.message,
            suggestion=issue.suggestion,
            context=f"\nAdditional context:\n{rag_context}" if rag_context else "",
        )
        raw = self._chat(prompt, use_cache=True)
        return parse_ai_analysis(issue.rule_id, raw)

    # ------------------------------------------------------------------
    # Public API — session-based chat
    # ------------------------------------------------------------------

    def create_session(self, report: AnalysisReport, score: float) -> object:
        """Create a stateful AISession pre-loaded with report context."""
        from sparkguardian.ai.session import AISession

        top_issues = "\n".join(
            f"  [{i.rule_id}] {i.severity.value}: {i.message} (line {i.location.line})"
            for i in report.active_issues[:5]
        )
        system = CHAT_SYSTEM_PROMPT.format(
            system=self._system_prompt,
            target=report.target,
            score=f"{score:.0f}",
            total=len(report.active_issues),
            critical=report.critical_count,
            top_issues=top_issues,
        )
        return AISession(
            model=self._model,
            base_url=self._base_url,
            system_prompt=system,
        )

    # ------------------------------------------------------------------
    # Public API — streaming
    # ------------------------------------------------------------------

    def stream_explain_issue(self, issue: Issue, rag_context: str = "") -> Iterator[str]:
        prompt = EXPLAIN_FINDING_PROMPT.format(
            rule_id=issue.rule_id,
            title=issue.title,
            severity=issue.severity.value,
            message=issue.message,
            suggestion=issue.suggestion,
            context=f"\nAdditional context:\n{rag_context}" if rag_context else "",
        )
        yield from self._stream(prompt)

    def stream_explain_plan(self, plan_text: str) -> Iterator[str]:
        prompt = EXPLAIN_PLAN_PROMPT.format(plan_text=plan_text)
        yield from self._stream(prompt)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_messages(self, prompt: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self._system_prompt:
            msgs.append({"role": "system", "content": self._system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def _chat(self, prompt: str, use_cache: bool = True) -> str:
        if use_cache:
            cached = self._cache.get(self._model, prompt)
            if cached is not None:
                return cached

        try:
            import httpx  # type: ignore[import]
            r = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": self._build_messages(prompt),
                    "stream": False,
                    "options": {"num_predict": 1024},
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            result: str = r.json()["message"]["content"]
            if use_cache:
                self._cache.set(self._model, prompt, result)
            return result
        except Exception as e:
            logger.error("Ollama chat error (model=%s): %s", self._model, e)
            return f"[AI unavailable: {e}]"

    def _stream(self, prompt: str) -> Iterator[str]:
        try:
            import httpx  # type: ignore[import]
            with httpx.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": self._build_messages(prompt),
                    "stream": True,
                },
                timeout=self._timeout,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    token = json.loads(line).get("message", {}).get("content", "")
                    if token:
                        yield token
        except Exception as e:
            logger.error("Ollama stream error: %s", e)
            yield f"[AI unavailable: {e}]"
