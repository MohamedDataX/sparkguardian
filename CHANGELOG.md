# Changelog

All notable changes to SparkGuardian will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-05-19

### Fixed
- `_import_ollama()` raising `RuntimeError` outside try/except in `LocalLLM._chat()` and `LocalLLM._stream()` — now caught gracefully so `remediation`, `analyze --ai`, and chat fall back to error string when the `ollama` package is missing (no `[ai]` extra installed).
- Added unit tests verifying graceful degradation when `ollama` package is absent.

## [0.1.0] — 2026-05-19

### Added — Initial public release
- Static AST analysis via `libcst` (never executes user code)
- 16 static rules (CY001–CY020) — reliability, cost, clarity, UDF
- 5 dynamic execution plan rules (CY050–CY054)
- Safe auto-refactoring engine with backup, dry-run, and interactive modes
- Local AI integration via Ollama (deepseek-coder, codellama, llama3, mistral)
- RAG knowledge base — 24 entries from official Apache Spark 4.1.1 documentation
- AI structured output (`AIAnalysis`) + heuristic fallback
- Multi-turn AI chat session with conversation history
- Remediation planner (LLM-driven + heuristic fallback)
- LRU response cache (128 entries, hit-rate tracking)
- 5 report formats: terminal (Rich), JSON, Markdown, HTML, SARIF v2.1.0
- Cloud cost estimator — AWS EMR, Databricks, GCP Dataproc, Azure Synapse
- Longitudinal audit history with regression detection + CSV export
- 0–100 performance scoring across reliability/cost/clarity dimensions
- Rule governance — enable/disable, severity override per project
- `cy:ignore` suppression engine (inline + block) with audit trail
- TOML and YAML configuration support
- CI/CD examples — GitHub Actions, GitLab CI, Jenkins
- Exit codes 0/1/2 for CI integration
- 9 CLI commands: `analyze`, `fix`, `explain-plan`, `list-rules`, `ai-status`,
  `remediation`, `chat`, `cost`, `history`
- 373 unit tests · 0 failures · 0 warnings · 0 ruff errors

[0.1.1]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.1
[0.1.0]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.0
