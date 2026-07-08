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
- [Architecture](#architecture)
- [Development](#development)

---

## Features

| Feature | Description |
|---------|-------------|
| **Static AST Analysis** | Deterministic analysis via `libcst` : never executes user code |
| **Execution Plan Analysis** | Parses `df.explain()` output, detects shuffles / CartesianProduct / AQE |
| **Safe Auto-Refactoring** | Rewrites code with backup, dry-run preview, interactive mode |
| **Local AI Assistant** | Ollama-powered explanations, structured analysis, remediation plans |
| **AI Chat Session** | Interactive multi-turn chat about findings with history management |
| **RAG Knowledge Base** | 24 entries from official Apache Spark 4.1.1 docs : no external vector DB |
| **Performance Scoring** | 0-100 score across reliability - cost - and clarity dimensions |
| **CI/CD Integration** | Exit codes 0/1/2 - GitHub Actions, GitLab CI, Jenkins |
| **Rule Governance** | Enable/disable rules, override severity, per-project config (TOML/YAML) |
| **Ignore System** | `# cy:ignore CY008` inline and block suppression with audit trail |
| **Rich Reporting** | Terminal, JSON, Markdown, HTML, **SARIF v2.1.0** |
| **Cloud Cost Estimator** | Translates anti-patterns into **$waste** on AWS EMR / Databricks / GCP / Azure |
| **Audit History** | Longitudinal tracking with regression detection + CSV export |

---

## Installation

```bash
pip install sparkguardian              # core
pip install "sparkguardian[ai]"        # + local Ollama integration
```

**From source:**

```bash
git clone https://github.com/MohamedDataX/sparkguardian
cd sparkguardian
pip install -e ".[dev]"
```

**Verify:**

```bash
sparkguardian --version          # SparkGuardian v0.1.1
sparkguardian --help             # 9 commands
sparkguardian analyze app.py
```

**Requirements:** Python 3.11+ - Tested on 3.11 / 3.12 / 3.13

---

## Quick Start

```bash
# Analysis (5 output formats)
sparkguardian analyze app.py                       # terminal
sparkguardian analyze app.py --json                # CI integration
sparkguardian analyze app.py --html report.html    # dashboard
sparkguardian analyze app.py --md report.md        # GitHub PR comment
sparkguardian analyze app.py --sarif report.sarif  # GitHub Code Scanning

# Auto-fix
sparkguardian fix app.py --dry-run                 # preview diff
sparkguardian fix app.py --interactive             # per-fix prompt
sparkguardian fix app.py                           # apply + backup

# Execution plan
sparkguardian explain-plan plan.txt

# Rules + config
sparkguardian list-rules

# AI (Ollama)
sparkguardian ai-status
sparkguardian analyze app.py --ai
sparkguardian remediation app.py
sparkguardian chat app.py

# Cloud cost
sparkguardian cost app.py
sparkguardian cost app.py --data-tb 5 --nodes 30 --cloud databricks

# History
sparkguardian analyze app.py --history             # record snapshot
sparkguardian history                              # view evolution
sparkguardian history --csv evolution.csv          # research export
```

---

## Exit Codes

| Code | Meaning | CI behavior |
|------|---------|-------------|
| `0` | No issues | Build passes |
| `1` | CRITICAL issue found | Build **fails** |
| `2` | Warnings only | Build passes (configurable) |

---

## Rules

### Static - AST Analysis (16 rules)

| Rule | Title | Severity | Impact |  |
|------|-------|----------|--------|:-------:|
| CY001 | `.collect()` - driver memory risk | HIGH | RELIABILITY | |
| CY002 | `.toPandas()` - large local materialization | HIGH | RELIABILITY | |
| CY003 | `.count()` abuse - full scan triggered | MEDIUM | COST | |
| CY004 | Spark action inside loop | **CRITICAL** | RELIABILITY | |
| CY005 | `.show()` in production code | LOW | RELIABILITY | |
| CY008 | `repartition(1)` detected | HIGH | COST |  |
| CY009 | Chained `withColumn()` (5+) | MEDIUM | COST | |
| CY010 | Implicit join - missing `how=` | LOW | CLARITY | |
| CY011 | `select("*")` - broad column selection | LOW | CLARITY | |
| CY012 | `cache()`/`persist()` - verify necessity | LOW | COST | |
| CY013 | Repeated scan of same data source | HIGH | COST | |
| CY014 | `filter()` after `groupBy()` - reorder | MEDIUM | COST | |
| CY016 | `crossJoin()` - explicit CartesianProduct | HIGH | COST | |
| CY017 | `distinct()` - full shuffle | MEDIUM | COST | |
| CY018 | `orderBy()` without `limit()` - global sort | MEDIUM | COST | |
| CY020 | Python UDF - use native SQL functions | HIGH | COST | |

### Dynamic - Execution Plan (5 rules)

| Rule | Title | Severity | Impact |
|------|-------|----------|--------|
| CY050 | `CartesianProduct` node detected | **CRITICAL** | COST |
| CY051 | Excessive shuffle (`Exchange`) nodes | HIGH | COST |
| CY052 | `SortMergeJoin` - broadcast opportunity | MEDIUM | COST |
| CY053 | Window function without `partitionBy` | HIGH | COST |
| CY054 | AQE (`AdaptiveSparkPlan`) not active | MEDIUM | COST |

---

## Ignore System

```python
# Inline
df.repartition(1)  # cy:ignore CY008

# Block
# cy:ignore-start CY008
df_single = df.repartition(1)
df_single.write.parquet("output/")
# cy:ignore-end CY008
```

Ignored findings remain in reports as suppressed (use `--show-ignored`)

---

## Configuration

Create `.sparkguardian.toml` (or `.yaml`) at project root:

```toml
[sparkguardian]
fail_on_critical = true
fail_on_high = false
warning_threshold = 10
ignore_paths = ["tests/", "examples/"]

[rules.CY008]
enabled = true
severity = "HIGH"

[rules.CY005]
enabled = false
```

---

## Local AI Setup

All inference runs locally via [Ollama](https://ollama.ai). **No data leaves your machine**

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull deepseek-coder:6.7b   # recommended
ollama serve
sparkguardian ai-status
```

### Supported Models

| Model | Pull command | Notes |
|-------|-------------|-------|
| DeepSeek-Coder 6.7B | `ollama pull deepseek-coder:6.7b` | **Recommended** |
| CodeLlama 7B | `ollama pull codellama:7b` | Good code quality |
| Llama 3 8B | `ollama pull llama3:8b` | General purpose |
| Mistral 7B | `ollama pull mistral:7b` | Fast inference |

Auto-selects first available model from this list.

### AI Architecture

```
LocalLLM
├── LRU response cache (128 entries, hit-rate tracking)
├── System prompt injection (role anchor)
├── Structured JSON output parsing (AIAnalysis dataclass)
├── Streaming support (token-by-token terminal output)
└── Auto model selection

AISession (multi-turn chat)
├── Conversation history with automatic trimming
├── Context injection (RAG knowledge base)
└── Reset / turn counting

RemediationPlanner
├── LLM-driven: priority_order, effort_estimate, quick_wins, blockers
└── Heuristic fallback (deterministic, works without Ollama)

SparkKnowledgeBase (RAG)
├── 24 entries from official Apache Spark 4.1.1 documentation
│   tuning.html / sql-performance-tuning.html / rdd-programming-guide.html
├── query(question, rule_id) - lookup by rule_id or keyword scoring
├── query_with_config(rule_id) => (content, config_params[])
├── get_config_params(rule_id) => list[str]
└── sources() => list[str]
```

---

## Cloud Cost Estimator

Translates detected anti-patterns into **estimated USD waste** on major cloud providers.

```bash
sparkguardian cost examples/bad_pipeline.py
# 💸 Estimated waste: $2,407/month ($28,884/year)

sparkguardian cost prod/ --data-tb 50 --nodes 100 --cloud databricks
# 💸 Estimated waste: $156,420/month ($1,877,040/year)

sparkguardian cost app.py --json   # FinOps integration
```

**Pricing methodology (2025-2026 baseline):**
- AWS EMR on-demand: ~$0.063/vCPU-hour
- Databricks DBU: $0.40/DBU-hour - ×1.3 vs EMR
- GCP Dataproc: ×0.9 vs EMR / Azure Synapse: ×1.1 vs EMR
- S3: $0.023/GB stored + $0.005/1k GET requests
- Cross-AZ egress: $0.09/GB

Each rule has a calibrated cost model factoring severity, occurrence count (sub-linear), and workload scale

---

## Audit History

Track quality evolution across commits, releases, or daily runs.

```bash
sparkguardian analyze . --history             # record snapshot
sparkguardian history                         # view evolution
# ↘️ Latest delta: -8.5
# ⚠️ REGRESSION DETECTED (delta > -5)

sparkguardian history --csv evolution.csv     # research export
sparkguardian history --target src/foo.py    # filter
```

Snapshots stored in `.sparkguardian-history.json` with git commit/branch metadata.

---

## SARIF Output

Native integration with GitHub Code Scanning, GitLab SAST, Azure DevOps, SonarQube

```yaml
- name: SparkGuardian
  run: sparkguardian analyze . --sarif sparkguardian.sarif
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sparkguardian.sarif
```

Findings appear directly in GitHub **Security** tab with severity-graded PR annotations

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: SparkGuardian Audit
  run: sparkguardian analyze . --json > report.json
  # Exit 1 on CRITICAL => build fails automatically
```

Full example: [`.github/workflows/sparkguardian.yml`](.github/workflows/sparkguardian.yml)

### GitLab CI

```yaml
sparkguardian:
  script: sparkguardian analyze . --json > report.json
```

Full example: [`ci/gitlab-ci.yml`](ci/gitlab-ci.yml)

### Jenkins

See [`ci/Jenkinsfile`](ci/Jenkinsfile) for a pipeline with HTML report archiving

---

## Architecture

```
sparkguardian/
├── cli.py                    # Typer CLI (9 commands)
├── config.py                 # TOML/YAML loader
├── constants.py
│
├── parser/                   # libcst static + execution plan analysis
│   ├── ast_analyzer.py
│   ├── plan_analyzer.py
│   ├── execution_parser.py
│   ├── ignore_handler.py     # cy:ignore engine
│   └── node_extractors.py
│
├── rules/                    # 16 static + 5 dynamic = 21 rules
│   ├── base.py               # BaseRule ABC
│   ├── registry.py           # @register decorator
│   ├── static_rules.py
│   └── dynamic_rules.py
│
├── models/                   # Issue, Report, ExecutionNode
├── rewriter/                 # SafeRewriter + libcst transformers
│
├── ai/                       # Local Ollama integration
│   ├── local_llm.py          # LLM client (cache + streaming)
│   ├── session.py            # Multi-turn chat history
│   ├── remediation.py        # LLM + heuristic fallback
│   ├── structured.py         # AIAnalysis JSON parser
│   ├── cache.py              # LRU AIResponseCache
│   ├── rag.py                # SparkKnowledgeBase (24 entries)
│   └── prompts.py            # Versioned prompt library
│
├── reporting/                # terminal / json / md / html / SARIF
├── scoring/                  # 0–100 performance score
├── cost/                     # Cloud cost models (EMR/Databricks/GCP/Azure)
├── history/                  # Longitudinal audit snapshots
├── ci/                       # Exit code logic
└── utils/                    # logger, file_utils
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/test_ast.py -v               # specific module
pytest tests/ --cov=sparkguardian         # with coverage
```

| Test file | Covers |
|-----------|--------|
| `test_ai.py` | LLM cache, session, structured output, remediation, prompts |
| `test_ast.py` | All 16 static rules, analyzer edge cases, ignore system |
| `test_ci.py` | Exit codes (0/1/2) |
| `test_config.py` | TOML, YAML, defaults, rule overrides |
| `test_file_utils.py` | backup_file, collect_python_files |
| `test_ignore.py` | cy:ignore inline and block directives |
| `test_models.py` | Issue, Location, AnalysisReport, ExecutionNode |
| `test_node_extractors.py` | NodeType classification, plan parser |
| `test_plan.py` | Dynamic rules, execution plan analysis |
| `test_rag.py` | Knowledge base entries, keyword search, config params, sources |
| `test_registry.py` | Rule registry, @register decorator |
| `test_reporting.py` | JSON, Markdown, HTML reporters |
| `test_rewriter.py` | CST transformer, diff generator |
| `test_safe_rewriter.py` | SafeRewriter dry-run, apply, backup |
| `test_scoring.py` | 0–100 score engine, penalty matrix |
| `test_cost.py` | Cloud cost estimator (4 clouds, workload scaling) |
| `test_sarif.py` | SARIF v2.1.0 format compliance, severity mapping |
| `test_history.py` | Audit history, CSV export, regression detection |

---

## License

[MIT](LICENSE) © SparkGuardian Contributors
