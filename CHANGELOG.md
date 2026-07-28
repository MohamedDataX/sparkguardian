# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.3] — 2026-07-23

### Added
- Licensing portal (FastAPI) with free community tokens, admin dashboard, and
  Docker / Fly.io / AWS Lambda deployment configs.
- CLI license gate: `activate`, `license`.

### Changed
- Cost model rewritten around wasted compute-time × real cloud pricing instead
  of hardcoded monthly amounts.
- README and docs overhaul.

### Removed
- Stripe billing. Tokens are free and the project is fully open source.

## [0.1.2] — 2026-07-09

### Changed
- License portal defaults to the deployed URL.

## [0.1.1] — 2026-05-19

### Fixed
- `LocalLLM` no longer crashes when the optional `ollama` package is missing;
  `remediation`, `analyze --ai`, and `chat` degrade to an error message.

## [0.1.0] — 2026-05-19

Initial public release.

### Added
- Static AST analysis with `libcst` — never executes the code it analyzes.
- 21 rules: 16 static (CY001–CY020) + 5 execution-plan rules (CY050–CY054).
- Auto-refactoring with backup, dry-run, and interactive modes.
- Local AI via Ollama, backed by a 24-entry RAG knowledge base built from the
  Apache Spark docs. Heuristic fallback when no model is available.
- Cloud cost estimator (AWS EMR, Databricks, GCP Dataproc, Azure Synapse).
- 0–100 score across reliability, cost, and clarity.
- 5 report formats: terminal, JSON, Markdown, HTML, SARIF 2.1.0.
- Audit history with regression detection.
- `cy:ignore` suppressions, per-project rule config (TOML/YAML).
- CI integration: exit codes 0/1/2, examples for GitHub Actions, GitLab, Jenkins.

[0.1.3]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.3
[0.1.2]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.2
[0.1.1]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.1
[0.1.0]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.0
