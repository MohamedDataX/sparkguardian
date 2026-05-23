"""SparkGuardian AI module — local-only Ollama integration."""
from sparkguardian.ai.cache import AIResponseCache
from sparkguardian.ai.local_llm import LocalLLM
from sparkguardian.ai.rag import KnowledgeEntry, SparkKnowledgeBase
from sparkguardian.ai.remediation import RemediationPlanner
from sparkguardian.ai.session import AISession
from sparkguardian.ai.structured import AIAnalysis, RemediationPlan

__all__ = [
    "LocalLLM",
    "AISession",
    "AIResponseCache",
    "SparkKnowledgeBase",
    "KnowledgeEntry",
    "RemediationPlanner",
    "AIAnalysis",
    "RemediationPlan",
]
