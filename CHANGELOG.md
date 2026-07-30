# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] — 2026-07-30

### Added
- S3-backed storage for the licensing portal, so it can run on AWS Lambda where
  the filesystem is wiped between invocations.

### Changed
- The AI features now call the Ollama server directly over HTTP instead of going
  through the `ollama` Python package. One less dependency to install.
- The GitHub Actions workflow reports findings without failing the build. The
  strict version is still there, just disabled by default.

### Fixed
- `analyze` no longer stops to ask for a license token in CI, where nobody can
  answer the prompt.
- `activate` pointed at the old Fly.io portal, which is gone. The packages
  published as 0.1.3 and earlier could not reach it, so activation failed with an
  SSL error. The default server is now the AWS endpoint. Set
  `SPARKGUARDIAN_API_URL` to point at your own portal instead.

## [0.1.3] — 2026-07-23

### Added
- Cost estimation now uses real cloud prices. Instead of guessing a monthly
  amount per rule, each anti-pattern is described by the compute time it wastes,
  which is then multiplied by the actual hourly price of the cluster. Prices come
  from AWS, Databricks, GCP and Azure public rates.
- Rules also say how their cost grows with data volume (fixed, linear, quadratic,
  or shuffle-bound), so the estimate follows the size of the pipeline.

### Changed
- README rewritten to explain the cost model and how to read the numbers.

### Removed
- Stripe payments. There is no paid plan anymore: tokens are free and the project
  is fully open source. Everything related to billing was deleted.

## [0.1.2] — 2026-07-09

### Added
- A web portal (FastAPI) where a user enters a name and an email and gets a free
  license token. The CLI can then activate that token with
  `sparkguardian activate` and check it with `sparkguardian license`.
- An admin page listing issued licenses, with revocation and basic stats,
  protected by a bearer token.
- Deployment files for Fly.io (`fly.toml`) plus a Dockerfile. The Fly setup uses
  a volume so the database survives restarts.

### Changed
- The CLI points to the deployed portal by default, so activation works without
  configuring anything. The URL stays overridable for self-hosting.
- Clearer error messages and email validation in the web form.

## [0.1.1] — 2026-05-19

### Fixed
- The AI commands crashed when the optional `ollama` package was not installed.
  They now show a message and the static analysis keeps working.

## [0.1.0] — 2026-05-19

First public release.

### Added
- Static analysis of PySpark code with `libcst`. The code is read, never
  executed, so it is safe to run on any pipeline.
- 21 rules in total: 16 read the source code (CY001–CY020) and 5 read the Spark
  execution plan (CY050–CY054).
- Automatic fixing of some issues, with a backup, a dry-run mode and an
  interactive mode.
- A local AI assistant based on Ollama, with a small knowledge base built from
  the Apache Spark documentation. If no model is available, a simpler rule-based
  explanation is used instead.
- A first version of the cost estimator for AWS EMR, Databricks, GCP Dataproc
  and Azure Synapse.
- A score from 0 to 100 covering reliability, cost and clarity.
- Reports in 5 formats: terminal, JSON, Markdown, HTML and SARIF.
- History of past audits, to detect regressions between two runs.
- `cy:ignore` comments to silence a rule, and per-project configuration in TOML
  or YAML.
- CI integration: exit codes 0/1/2 and example files for GitHub Actions, GitLab
  and Jenkins.

[Unreleased]: https://github.com/MohamedDataX/sparkguardian/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.4
[0.1.3]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.3
[0.1.2]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.2
[0.1.1]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.1
[0.1.0]: https://github.com/MohamedDataX/sparkguardian/releases/tag/v0.1.0
