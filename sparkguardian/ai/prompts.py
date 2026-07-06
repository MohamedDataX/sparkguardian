"""Prompt library — versioned, few-shot, system-injected."""
from __future__ import annotations

# System prompt — injected once per session as role anchor


SYSTEM_PROMPT = """You are SparkGuardian AI, an expert in Apache Spark internals,
PySpark optimization, and distributed computing performance engineering.

Your role:
- Diagnose PySpark anti-patterns with precise technical depth
- Reference Spark's execution model (DAG, stages, tasks, shuffle, Catalyst, Tungsten)
- Provide concrete, runnable code fixes
- Be concise — no filler, no hedging

Rules you must follow:
- Never suggest sending data to external services
- Always prefer native pyspark.sql.functions over Python UDFs
- Cite specific Spark configuration keys when relevant (e.g. spark.sql.adaptive.enabled)
- When giving code examples, use realistic variable names (df, spark, etc.)"""



# Structured JSON analysis prompt — returns parseable output


STRUCTURED_ANALYSIS_PROMPT = """Analyze this PySpark issue and respond with valid JSON only.
No prose outside the JSON block.

Issue:
  rule_id: {rule_id}
  title: {title}
  severity: {severity}
  message: {message}
  suggestion: {suggestion}
{context}

Respond with this exact JSON schema:
{{
  "explanation": "<2-3 sentence technical explanation of why this is a problem>",
  "spark_internals": "<what happens at JVM/DAG/shuffle level>",
  "code_before": "<minimal bad PySpark snippet illustrating the issue>",
  "code_after": "<corrected version of the same snippet>",
  "confidence": <float 0.0-1.0 — how certain you are this is a real problem>,
  "tags": ["<tag1>", "<tag2>"],
  "estimated_impact": "<LOW|MEDIUM|HIGH|CRITICAL>"
}}"""


# ---------------------------------------------------------------------------
# Plain explain prompt — for streaming terminal output
# ---------------------------------------------------------------------------

EXPLAIN_FINDING_PROMPT = """Diagnose this PySpark issue concisely.

Rule: {rule_id} — {title}
Severity: {severity}
Message: {message}
Suggestion: {suggestion}
{context}

Answer in exactly 3 sections:
**WHY** — root cause at the Spark execution level (1-2 sentences)
**IMPACT** — what goes wrong at scale (1 sentence)
**FIX** — corrected PySpark code snippet (code block only, no prose)"""


# ---------------------------------------------------------------------------
# Execution plan prompt — few-shot anchored
# ---------------------------------------------------------------------------

EXPLAIN_PLAN_PROMPT = """Translate this Spark execution plan into a structured diagnosis.

Example input:
  Exchange hashpartitioning(dept#1, 200)
  +- HashAggregate(keys=[dept#1])
Example output:
  SHUFFLE: HashAggregate triggers a full shuffle to co-locate dept keys.
  FIX: Pre-bucket the table on dept to eliminate this Exchange node.

Now analyze:
{plan_text}

Output format — one line per significant node:
  <NODE_TYPE>: <what it does> → <cost implication>
Then a SUMMARY section with top 3 optimization recommendations."""


# ---------------------------------------------------------------------------
# Refactor prompt — minimal, code-only output
# ---------------------------------------------------------------------------

SUGGEST_REFACTOR_PROMPT = """Fix this PySpark code. Output the corrected snippet only — no prose.

Issue: [{rule_id}] {suggestion}

```python
{code}
```

Corrected code:"""


# ---------------------------------------------------------------------------
# Remediation plan prompt
# ---------------------------------------------------------------------------

REMEDIATION_PLAN_PROMPT = """You are reviewing a SparkGuardian audit report.

File: {target}
Score: {score}/100
Issues found ({total} total):
{issues_text}

Generate a prioritized remediation plan. Respond with valid JSON only:
{{
  "priority_order": ["<rule_id1>", "<rule_id2>", ...],
  "effort_estimate": {{
    "<rule_id>": "<minutes|hours|days>"
  }},
  "quick_wins": ["<rule_id of issues fixable in < 30 min>"],
  "blockers": ["<rule_id of CRITICAL issues that must be fixed before production>"],
  "summary": "<2 sentence executive summary of the audit>",
  "roi_statement": "<1 sentence on expected performance/cost improvement after fixes>"
}}"""


# ---------------------------------------------------------------------------
# Chat / Q&A prompt — for interactive session
# ---------------------------------------------------------------------------

CHAT_SYSTEM_PROMPT = """{system}

Context — audit results for '{target}':
Score: {score}/100 | Issues: {total} | Critical: {critical}

Top findings:
{top_issues}

Answer questions about these findings. Be precise and actionable."""
