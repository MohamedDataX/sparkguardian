"""LRU cache for LLM responses.

Local inference costs seconds per call, and analysing a file re-asks the same
question for every occurrence of a rule. Process-local only: nothing is written
to disk, so no analysed code outlives the run.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CacheEntry:
    response: str
    model: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    hits: int = 0


class AIResponseCache:
    def __init__(self, max_size: int = 128) -> None:
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self.total_hits = 0
        self.total_misses = 0

    # ------------------------------------------------------------------

    def _key(self, model: str, prompt: str) -> str:
        # Model is part of the key: the same prompt answered by a different
        # model is a different answer.
        raw = f"{model}::{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, model: str, prompt: str) -> str | None:
        key = self._key(model, prompt)
        if key in self._cache:
            # move_to_end is what makes the OrderedDict an LRU: the least
            # recently used entry stays at the front, ready to be evicted.
            self._cache.move_to_end(key)
            self._cache[key].hits += 1
            self.total_hits += 1
            return self._cache[key].response
        self.total_misses += 1
        return None

    def set(self, model: str, prompt: str, response: str) -> None:
        key = self._key(model, prompt)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = CacheEntry(response=response, model=model)

    def clear(self) -> None:
        self._cache.clear()
        self.total_hits = 0
        self.total_misses = 0

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self.total_hits + self.total_misses
        return self.total_hits / total if total > 0 else 0.0

    def stats(self) -> dict[str, object]:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self.total_hits,
            "misses": self.total_misses,
            "hit_rate": f"{self.hit_rate:.1%}",
        }
