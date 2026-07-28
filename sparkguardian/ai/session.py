"""AISession — stateful multi-turn conversation with history + context window management."""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

import httpx

from sparkguardian.ai.prompts import SYSTEM_PROMPT
from sparkguardian.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_HISTORY = 20  # messages kept in context (system + user + assistant pairs)


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class AISession:
    """
    Stateful LLM session. Maintains conversation history.
    System prompt injected once. History truncated to _MAX_HISTORY.
    All inference stays local via Ollama.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_history: int = _MAX_HISTORY,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._max_history = max_history
        self._history: list[Message] = [Message(role="system", content=system_prompt)]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, question: str) -> str:
        self._history.append(Message(role="user", content=question))
        self._trim_history()
        response = self._call()
        self._history.append(Message(role="assistant", content=response))
        self._trim_history()
        return response

    def ask_stream(self, question: str) -> Iterator[str]:
        self._history.append(Message(role="user", content=question))
        self._trim_history()
        full = ""
        for token in self._stream():
            full += token
            yield token
        self._history.append(Message(role="assistant", content=full))
        self._trim_history()

    def reset(self, keep_system: bool = True) -> None:
        system = self._history[0] if self._history else None
        self._history = [system] if keep_system and system else []

    def inject_context(self, context: str) -> None:
        """Inject background knowledge as a system-side message."""
        self._history.append(Message(role="system", content=f"Context:\n{context}"))

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._history if m.role == "user")

    @property
    def history_text(self) -> str:
        return "\n".join(f"[{m.role}] {m.content[:80]}..." for m in self._history)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trim_history(self) -> None:
        # Keep system messages + last _max_history user/assistant messages
        system_msgs = [m for m in self._history if m.role == "system"]
        dialog_msgs = [m for m in self._history if m.role != "system"]
        if len(dialog_msgs) > self._max_history:
            dialog_msgs = dialog_msgs[-self._max_history :]
        self._history = system_msgs + dialog_msgs

    def _as_ollama_messages(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self._history]

    def _call(self) -> str:
        try:
            r = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": self._as_ollama_messages(),
                    "stream": False,
                    "options": {"num_predict": 1024},
                },
                timeout=120,
            )
            r.raise_for_status()
            return str(r.json()["message"]["content"])
        except Exception as e:
            logger.error("Session chat error: %s", e)
            return f"[AI error: {e}]"

    def _stream(self) -> Iterator[str]:
        try:
            with httpx.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": self._as_ollama_messages(),
                    "stream": True,
                },
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    token = json.loads(line).get("message", {}).get("content", "")
                    if token:
                        yield token
        except Exception as e:
            logger.error("Session stream error: %s", e)
            yield f"[AI error: {e}]"
