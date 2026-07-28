<p align="center">
  <img src="images/logo.jpeg" alt="SparkGuardian logo" width="120" />
</p>

<h1 align="center">SparkGuardian</h1>

<p align="center">
  <em>A production-grade auditing, optimization, and FinOps engine for Apache Spark — 100% offline.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/sparkguardian/"><img alt="PyPI" src="https://img.shields.io/pypi/v/sparkguardian?color=blue&label=PyPI" /></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB" />
  <img alt="Rules" src="https://img.shields.io/badge/rules-21-blue" />
  <img alt="Tests" src="https://img.shields.io/badge/tests-378%20passing-brightgreen" />
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

---

SparkGuardian reads your PySpark code **without ever executing it**, detects the
anti-patterns that quietly waste cluster money and crash jobs in production,
tells you what each one costs per month in real cloud dollars, and — when you
ask — rewrites them for you. A local AI layer explains every finding in plain
language, grounded in the official Spark documentation so it never invents an
answer. Nothing leaves your machine.

It was built to answer three questions a data engineer actually has:

> *"Where is my Spark code slow or fragile?"*  ·  *"What is that costing me?"*  ·  *"How do I fix it?"*

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [How it works — the engineering](#how-it-works--the-engineering)
  - [1 · The rule engine (static + dynamic)](#1--the-rule-engine-static--dynamic)
  - [2 · The FinOps cost model](#2--the-finops-cost-model)
  - [3 · RAG-grounded local AI](#3--rag-grounded-local-ai)
  - [4 · Safe auto-refactor](#4--safe-auto-refactor)
  - [5 · Scoring, history & CI](#5--scoring-history--ci)
- [Technology choices](#technology-choices)
- [Development](#development)
- [License](#license)

---

## Features

| Capability | What I built |
|---|---|
| **Static analysis** | A 21-rule engine that inspects the code's syntax tree — 16 source-level rules + 5 that read Spark execution plans. Never runs your code. |
| **FinOps cost model** | Translates each anti-pattern into `$ / month` using a time-and-complexity model and **live cloud pricing** (AWS & Azure APIs, with an offline fallback). |
| **RAG-grounded AI** | A local LLM (Ollama) explains findings, answering from a hand-curated knowledge base of official Spark docs — so explanations cite real config, not hallucinations. |
| **Safe auto-refactor** | Applies reviewable rewrites with a backup and a dry-run diff preview — refuses to touch anything it can't rewrite safely. |
| **Performance score** | A 0–100 health score with category breakdown, tracked over time to catch regressions between commits. |
| **Reports everywhere** | Terminal, JSON, Markdown, HTML, and **SARIF v2.1.0** for GitHub Code Scanning. |
| **CI/CD native** | Exit codes `0`/`1`/`2` and ready-made GitHub Actions, GitLab, and Jenkins recipes. |
| **Suppression system** | Inline and block-level `# cy:ignore` with a full audit trail. |

## Installation

```bash
pip install sparkguardian
```

Python 3.11+. The core install has a small, deliberate dependency set.

**Local AI needs no extra package.** SparkGuardian talks to a running
[Ollama](https://ollama.ai) server over its HTTP REST API using `httpx` (a core
dependency). Just start Ollama and pull a model:

```bash
ollama serve
ollama pull deepseek-coder:6.7b
```

## Usage

```bash
# 1. Activate once (free token — never expires, validates offline afterwards)
sparkguardian activate

# 2. Audit — anti-patterns, severity, performance score
sparkguardian analyze app.py
sparkguardian analyze src/ --sarif results.sarif      # also: --json --html --md

# 3. See what it costs, in real cloud dollars
sparkguardian cost app.py --cloud databricks --data-tb 10 --nodes 50 --runs 4

# 4. Fix it — preview first, then apply
sparkguardian fix app.py --dry-run
sparkguardian fix app.py

# 5. Ask the local AI (needs Ollama)
sparkguardian analyze app.py --ai
sparkguardian remediation app.py       # prioritized, AI-written fix plan

# Inspect a saved execution plan
sparkguardian explain-plan plan.txt
sparkguardian list-rules
```

## Configuration

A `.sparkguardian.toml` at the repo root controls everything — enable/disable
rules, override severities, ignore paths, and set the CI failure threshold:

```toml
[rules]
CY020 = { enabled = true, severity = "high" }   # Python UDFs
CY008 = { enabled = true }                       # repartition(1)

[ignore]
paths = ["tests/", "notebooks/"]

[ci]
fail_on = "high"        # exit non-zero if any high/critical issue remains
```

Suppress individual findings inline, with an auditable reason:

```python
df.collect()                       # cy:ignore CY001 — dataset is bounded to 100 rows
# cy:ignore-start CY008
df.repartition(1).write.csv(path)  # single-file export required downstream
# cy:ignore-end CY008
```

## Architecture

SparkGuardian is a pipeline: source code flows through parsing, into a rule
engine, and out to a set of independent consumers (scoring, cost, AI, reports).
Each stage is decoupled, which is what lets the same 21 findings feed a terminal
table, a SARIF file, a dollar estimate, and an AI explanation without any of
them knowing about each other.

```
                        ┌─────────────────────────────────────────┐
   your .py file  ──▶   │  PARSER                                   │
                        │  syntax tree + execution-plan reader      │
                        └───────────────────┬───────────────────────┘
                                            │  normalized nodes
                        ┌───────────────────▼───────────────────────┐
                        │  RULE ENGINE                               │
                        │  21 rules · registry · severity · ignore   │
                        └───────────────────┬───────────────────────┘
                                            │  Issues (rule, line, severity)
        ┌──────────────┬────────────────────┼───────────────┬──────────────┐
        ▼              ▼                     ▼               ▼              ▼
   ┌─────────┐   ┌───────────┐        ┌────────────┐   ┌─────────┐   ┌──────────┐
   │ SCORING │   │ COST      │        │ AI + RAG   │   │REWRITER │   │REPORTING │
   │ 0–100   │   │ $ / month │        │ Ollama +   │   │ safe    │   │ term/json│
   │ + trend │   │ live price│        │ Spark KB   │   │ autofix │   │ md/html  │
   └─────────┘   └───────────┘        └────────────┘   └─────────┘   │ /SARIF   │
                                                                     └──────────┘
```

| Module | Responsibility |
|---|---|
| `parser/` | Turns code into an analyzable tree and parses `explain()` output into plan nodes. |
| `rules/` | The 21 rules, a self-registering rule registry, severity model, and the ignore system. |
| `cost/` | The FinOps estimator and the live cloud-pricing client. |
| `ai/` | Local-LLM client, the RAG knowledge base, remediation planner, and response cache. |
| `rewriter/` | Safe code transformation with backups and diff generation. |
| `scoring/` · `history/` | The 0–100 score engine and longitudinal snapshot tracking. |
| `reporting/` | Five output formats from one report object. |
| `licensing/` · `ci/` | Offline license verification and CI exit-code resolution. |

## How it works — the engineering

### 1 · The rule engine (static + dynamic)

The engine works on two levels. **Static rules** walk the code's concrete syntax
tree with exact line/column tracking, so every finding points at the precise
character span that caused it — no false line numbers, no running your code.
**Dynamic rules** read the text of a Spark execution plan and flag physical
operators that only appear at runtime (`CartesianProduct`, excessive
`Exchange`/shuffle stages, missed broadcast joins, single-partition windows,
disabled AQE).

Rules register themselves through a decorator, so the catalogue is extended by
adding one class — the parser and reporting layers never change. This clean
separation between *parsing* and *rule logic* is deliberate: the rules don't
know how the tree was built, which keeps each rule small and independently
testable.

**21 rules today:** 16 source-level (`CY001`–`CY020`) covering driver-OOM risks,
shuffle waste, missing column pruning, Python-UDF overhead, and more; plus 5
plan-level rules (`CY050`–`CY054`).

### 2 · The FinOps cost model

Most linters stop at "this is slow." SparkGuardian answers "this costs **$X/month**,"
using a model built on one honest formula:

```
cost  =  wasted_compute_time  ×  real_cluster_hourly_cost
```

Every rule carries an **algorithmic complexity class** — `FIXED`, `LINEAR`,
`QUADRATIC`, or `SHUFFLE_BOUND` — that describes how its wasted time grows with
data volume. A CartesianProduct's cost explodes quadratically with your data; a
stray `.show()` stays flat. The waste in minutes is then multiplied by the **real
hourly price** of your actual cluster, fetched live from the AWS and Azure
pricing APIs (Databricks DBU surcharge and spot discounts included), with a
verified offline price table as a transparent fallback so the tool never needs
credentials or a network to run.

The result scales the way a real cloud bill does — not with the naïve
"multiply everything together" heuristic it replaced.

```
$ sparkguardian cost pipeline.py --cloud databricks --data-tb 10 --nodes 50 --runs 4
💸 Estimated waste: $31,713/month  ($380,557/year)
```

### 3 · RAG-grounded local AI

This is the piece I'm proudest of. A local LLM is convenient but will happily
invent Spark config flags that don't exist. To stop that, SparkGuardian ships a
**Retrieval-Augmented Generation** layer built entirely in-house:

- A **curated knowledge base** of 24 entries distilled from the official Apache
  Spark 4.1.1 docs (the tuning guide, SQL performance tuning, and the RDD
  programming guide) — one per rule, plus core topics like shuffle-partition
  sizing, data skew, and broadcast variables. Each entry is tagged with keywords
  and carries the *exact* Spark config parameters and source URL that back it.
- A **keyword-overlap retriever** that scores entries against the question and
  returns the most relevant passage — no external vector database, no embedding
  service, no network. That is what keeps the "100% offline" promise real.
- The retrieved passage is injected into the LLM prompt as authoritative
  context, so the model's job is to *explain the retrieved facts*, not to recall
  them. Explanations end up citing real settings like
  `spark.sql.adaptive.enabled` and `spark.sql.autoBroadcastJoinThreshold`
  because those came from the knowledge base, not the model's imagination.

The effect: local, private, fast, and grounded — the AI is helpful without being
a liability.

### 4 · Safe auto-refactor

`fix` rewrites code through a transformer that only touches patterns it can
change **without altering behavior** — e.g. `repartition(1)` → `coalesce(1)`,
adding an explicit `how=` to a join. It always writes a backup, offers a
`--dry-run` unified diff, and an interactive mode to approve each change. If a
rewrite can't be proven safe, it's reported but never applied.

### 5 · Scoring, history & CI

Every audit produces a **0–100 performance score** with a per-category
breakdown. Recording snapshots over time turns that into **regression
detection** — a PR that drops the score gets flagged. For pipelines, a single
`--sarif` flag emits GitHub Code Scanning-native output, and the process exits
`0` (clean), `1` (critical), or `2` (warnings) so any CI system can gate on it.

## Technology choices

Each dependency was chosen for a specific reason — the tool leans on a few
well-picked libraries rather than a large stack.

| Choice | Why |
|---|---|
| **Concrete-syntax-tree parsing** | Preserves exact source positions and formatting, so findings are precise and auto-fixes don't reformat the file. Analysis is purely static — your code never executes. |
| **Local LLM via Ollama** | Keeps AI features fully offline and private; no source code is ever sent to a cloud API. Grounded by the in-house RAG layer. |
| **Custom keyword RAG (no vector DB)** | A vector database would add a heavy dependency and a service to run. For a bounded, curated corpus, keyword retrieval is accurate, instant, and dependency-free. |
| **SARIF v2.1.0 output** | The industry-standard format GitHub, GitLab, and security tooling already understand — zero custom integration needed. |
| **Typed, strict codebase** | Fully type-annotated and linted; **378 tests** cover the rule engine, cost model, RAG, rewriter, and reporting. |

## Development

```bash
pip install -e ".[dev]"
pytest                       # 378 tests
ruff check sparkguardian     # lint
mypy sparkguardian           # types
```

## License

MIT — see [LICENSE](LICENSE). SparkGuardian is free and open source; the
companion licensing portal in `application/` issues free tokens and is described
in its own [README](application/README.md).
