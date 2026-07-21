<p align="center">
  <img src="images/logo.jpeg" alt="SparkGuardian logo" width="120" />
</p>

<h1 align="center">SparkGuardian</h1>

<p align="center">
  <em>Production-grade PySpark auditing, optimization, and governance framework</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/sparkguardian/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/sparkguardian?color=blue&label=PyPI" /></a>
<a href="https://pypi.org/project/sparkguardian/">
  <img alt="Downloads" src="https://img.shields.io/badge/downloads-5-blue" />
</a>
  <img alt="Rules" src="https://img.shields.io/badge/rules-21-blue" />
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

<p align="center"><strong>Tech stack</strong></p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" />
  <img alt="Apache Spark / PySpark" src="https://img.shields.io/badge/Apache%20Spark-PySpark-E25A1C?logo=apachespark&logoColor=white" />
  <img alt="libcst" src="https://img.shields.io/badge/libcst-AST%20analysis-2E7CD8" />
  <img alt="Typer CLI" src="https://img.shields.io/badge/Typer-CLI-009485?logo=typer&logoColor=white" />
  <img alt="Rich terminal UI" src="https://img.shields.io/badge/Rich-Terminal%20UI-FCC624" />
  <img alt="Ollama local AI" src="https://img.shields.io/badge/Ollama-Local%20AI-000000?logo=ollama&logoColor=white" />
  <img alt="SARIF v2.1.0" src="https://img.shields.io/badge/SARIF-v2.1.0-orange" />
  <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=githubactions&logoColor=white" />
  <img alt="GitHub Code Scanning" src="https://img.shields.io/badge/GitHub%20Code%20Scanning-supported-181717?logo=github&logoColor=white" />
  <img alt="GitLab CI" src="https://img.shields.io/badge/GitLab%20CI-supported-FC6D26?logo=gitlab&logoColor=white" />
  <img alt="Jenkins" src="https://img.shields.io/badge/Jenkins-supported-D24939?logo=jenkins&logoColor=white" />
  <img alt="Rust (planned)" src="https://img.shields.io/badge/Rust-planned-CE412B?logo=rust&logoColor=white" />
</p>

---

SparkGuardian detects PySpark anti-patterns, analyzes execution plans, generates prioritized remediation plans, and integrates into CI/CD pipelines. All **100% offline**, no cloud APIs, no source code exfiltration

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Rules](#rules)
- [Ignore System](#ignore-system)
- [Configuration](#configuration)
- [Local AI Setup](#local-ai-setup)
- [Cloud Cost Estimator](#cloud-cost-estimator)
- [Audit History](#audit-history)
- [SARIF Output](#sarif-output)
- [CI/CD Integration](#cicd-integration)
- [Licensing & Web Portal](#licensing--web-portal)
- [Deployment](#deployment)
- [Architecture](#architecture)
- [Development](#development)

---

## Features

| Feature | Description |
|---|---|
| Static AST analysis | `libcst`, never executes your code — 21 rules |
| Execution-plan analysis | shuffles, CartesianProduct, AQE from `df.explain()` |
| Safe auto-refactor | backup + dry-run preview |
| Local AI (Ollama) | explanations, remediation, offline RAG |
| Cloud cost estimator | $ waste on EMR / Databricks / GCP / Azure |
| Score + history | 0–100 score, regression detection |
| Reports | terminal, JSON, Markdown, HTML, SARIF v2.1.0 |
| CI/CD | exit codes 0/1/2 — GitHub Actions, GitLab, Jenkins |
| Licensing | free community tokens, offline activation |

## Installation

```bash
pip install sparkguardian
pip install "sparkguardian[ai]"    # + local Ollama
```

Python 3.11+.

## Quick Start

```bash
sparkguardian activate             # paste SG-… token (free, never expires)
sparkguardian analyze app.py       # --json --html --md --sarif
sparkguardian fix app.py --dry-run
sparkguardian cost app.py --cloud databricks
sparkguardian explain-plan plan.txt
sparkguardian remediation app.py   # AI (needs Ollama)
sparkguardian license              # status
```

## Rules

21 rules — static AST (16) + execution-plan (5). List them:

```bash
sparkguardian list-rules
```

## Ignore System

Suppress inline or by block, with audit trail:

```python
df.collect()                       # cy:ignore CY001
# cy:ignore-start CY008
...
# cy:ignore-end CY008
```

## Configuration

`.sparkguardian.toml` — enable/disable rules, override severity, ignore paths, CI thresholds.

## Local AI Setup

Optional, 100% local via Ollama:

```bash
pip install "sparkguardian[ai]"
ollama pull llama3.1
sparkguardian ai-status
```

## Cloud Cost Estimator

Turns anti-patterns into $ waste per cloud:

```bash
sparkguardian cost app.py --cloud databricks
# 💸 Estimated waste: $2,407/month
```

## Audit History

Track score over time, flag regressions:

```bash
sparkguardian analyze app.py --history
sparkguardian history app.py
```

## SARIF Output

GitHub Code Scanning ready:

```bash
sparkguardian analyze src/ --sarif results.sarif
```

## CI/CD Integration

```yaml
- run: pip install sparkguardian
- run: sparkguardian analyze src/ --sarif results.sarif
```

Exit **0** clean · **1** critical · **2** warnings. GitLab / Jenkins samples in `ci/`.

## Licensing & Web Portal

`application/` — FastAPI landing page + free-token portal. **Live:** <https://sparkguardian-portal.fly.dev>

SparkGuardian is **free and open source (MIT)** — no paid tier, no billing. The
token only identifies the user and lets the CLI verify itself offline.

- Free community tokens, **never expire** (name + email → signed `SG-…`)
- Idempotent: same email always gets the same token back
- CLI activates online once, caches locally, then works **offline**
- Admin dashboard: list / revoke / stats

```bash
cd application && ./run.sh          # http://localhost:8000  (/admin, /docs)
```

## Deployment

Full app on any container host:

- **Fly.io** — `cd application && fly deploy` (`fly.toml` included)
- **Render** — Blueprint via `render.yaml`

See [`application/README.md`](application/README.md).

## Architecture

```
sparkguardian/   parser · rules · rewriter · ai · cost · scoring · history · reporting · licensing · cli
application/     backend (FastAPI)  ·  frontend (static portal)
```

## Development

```bash
pip install -e ".[dev]"
pytest                 # 375 tests
ruff check . && mypy sparkguardian
```

## License

MIT — see [LICENSE](LICENSE).
