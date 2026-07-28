"""Cost Estimator — translates anti-patterns into estimated cloud cost impact.

FinOps methodology:

    cost = wasted_compute_time  ×  real_cluster_hourly_cost

Each rule is modelled by the *compute-minutes it wastes per run* on a reference
cluster (10 nodes, 1 TB/day), plus how that waste scales with data volume
(``ComplexityType``). The dollar figure comes from a real per-instance hourly
price (see ``pricing_client``) multiplied by the actual cluster size — not from
hardcoded monthly amounts.

At the reference point (1 TB/day) every complexity multiplier equals 1, so a
rule's ``baseline_wasted_minutes`` is exactly its per-run waste there.

Pricing sources (verified 2025-2026):
  - AWS EC2/EMR on-demand per instance (m6g.xlarge = $0.154/h, us-east-1)
  - Databricks DBU = $0.15/DBU-hour (Jobs Compute, Premium), added on the VM
  - Spot/preemptible ≈ 65% cheaper than on-demand
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from sparkguardian.cost.pricing_client import CloudPricingFetcher
from sparkguardian.models.issue import Severity
from sparkguardian.models.report import AnalysisReport


class ComplexityType(Enum):
    """How a rule's wasted time scales with the daily data volume."""
    FIXED = "fixed"                # O(1)      — fixed cost per failure/run
    LINEAR = "linear"             # O(N)      — scales with data volume
    QUADRATIC = "quadratic"       # O(N^2)    — row explosions (cartesian, explode)
    SHUFFLE_BOUND = "shuffle"     # O(N log N)— shuffle-dominated cost


@dataclass
class AlgorithmicCostModel:
    """Time-and-complexity cost model for one rule.

    ``baseline_wasted_minutes`` is the extra compute-minutes this anti-pattern
    burns in a single run on the reference cluster (10 nodes, 1 TB/day). For
    rules describing occasional failures (e.g. driver OOM) it is the value
    already amortised across runs.
    """
    rule_id: str
    category: str                 # "compute" | "storage" | "network" | "io"
    complexity: ComplexityType
    baseline_wasted_minutes: float
    factor_description: str


# Per-rule cost models — reference cluster: 10 nodes, 1 TB/day, 1 run/day.
# baseline_wasted_minutes = extra compute-minutes per run at that reference.

_COST_MODELS: dict[str, AlgorithmicCostModel] = {
    # --- Reliability: crashes/reruns → amortised fixed waste per run ---
    "CY001": AlgorithmicCostModel(
        "CY001", "compute", ComplexityType.FIXED, 4.0,
        "Driver .collect() OOM → job rerun (amortised over ~1-2 crashes/month)",
    ),
    "CY002": AlgorithmicCostModel(
        "CY002", "compute", ComplexityType.FIXED, 6.0,
        "toPandas() pulls all rows to driver → OOM + rerun, amortised",
    ),
    "CY003": AlgorithmicCostModel(
        "CY003", "io", ComplexityType.LINEAR, 3.0,
        "Repeated full scans — extra reads scale with data volume",
    ),

    # --- Critical: repeated jobs / row explosions ---
    "CY004": AlgorithmicCostModel(
        "CY004", "compute", ComplexityType.LINEAR, 12.0,
        "Spark action inside a loop — N jobs instead of 1, scales with data",
    ),
    "CY005": AlgorithmicCostModel(
        "CY005", "compute", ComplexityType.FIXED, 0.5,
        "Stray .show() in production — extra action + stdout overhead",
    ),

    # --- Shuffle-bound: the #1 Spark expense ---
    "CY008": AlgorithmicCostModel(
        "CY008", "compute", ComplexityType.SHUFFLE_BOUND, 8.0,
        "repartition(1)/coalesce(1) — full shuffle into a single partition",
    ),
    "CY009": AlgorithmicCostModel(
        "CY009", "compute", ComplexityType.LINEAR, 1.5,
        "Deep chained withColumn plan — Catalyst planning + per-row overhead",
    ),
    "CY010": AlgorithmicCostModel(
        "CY010", "compute", ComplexityType.FIXED, 0.5,
        "Implicit inner join — silent data loss, minor compute",
    ),
    "CY011": AlgorithmicCostModel(
        "CY011", "io", ComplexityType.LINEAR, 3.0,
        "No column pruning (select *) — extra columnar I/O scales with data",
    ),
    "CY012": AlgorithmicCostModel(
        "CY012", "compute", ComplexityType.FIXED, 1.0,
        "cache()/persist() never used — wasted memory + eviction churn",
    ),
    "CY013": AlgorithmicCostModel(
        "CY013", "io", ComplexityType.LINEAR, 5.0,
        "Recompute instead of cache — duplicate scans + S3 API costs",
    ),
    "CY014": AlgorithmicCostModel(
        "CY014", "compute", ComplexityType.LINEAR, 2.5,
        "Filter applied late — larger shuffle/scan input than necessary",
    ),
    "CY016": AlgorithmicCostModel(
        "CY016", "compute", ComplexityType.QUADRATIC, 4.0,
        "explode/self-join blowup — N*M row growth, super-linear runtime",
    ),
    "CY017": AlgorithmicCostModel(
        "CY017", "compute", ComplexityType.SHUFFLE_BOUND, 3.0,
        "distinct()/dropDuplicates — full shuffle for deduplication",
    ),
    "CY018": AlgorithmicCostModel(
        "CY018", "compute", ComplexityType.SHUFFLE_BOUND, 3.5,
        "Global orderBy vs top-N — O(N log N) total sort",
    ),
    "CY020": AlgorithmicCostModel(
        "CY020", "compute", ComplexityType.LINEAR, 6.0,
        "Python UDF — 10-100x slower than native, per-row, scales with data",
    ),

    # --- Dynamic plan-level rules ---
    "CY050": AlgorithmicCostModel(
        "CY050", "compute", ComplexityType.QUADRATIC, 6.0,
        "CartesianProduct — N*M rows, can dominate the whole job",
    ),
    "CY051": AlgorithmicCostModel(
        "CY051", "network", ComplexityType.SHUFFLE_BOUND, 4.0,
        "Excessive shuffles — disk spill + cross-node network egress",
    ),
    "CY052": AlgorithmicCostModel(
        "CY052", "compute", ComplexityType.SHUFFLE_BOUND, 3.0,
        "Missed broadcast — sort+shuffle both sides instead of a map-side join",
    ),
    "CY053": AlgorithmicCostModel(
        "CY053", "compute", ComplexityType.SHUFFLE_BOUND, 3.5,
        "Window without partitionBy — single-partition, parallelism lost",
    ),
    "CY054": AlgorithmicCostModel(
        "CY054", "compute", ComplexityType.LINEAR, 2.5,
        "AQE disabled — static plan keeps skew/over-partitioning waste",
    ),
}


# Workload profile

@dataclass
class WorkloadProfile:
    """Concrete workload the pipeline runs on. Defaults = reference cluster."""
    daily_data_tb: float = 1.0
    cluster_nodes: int = 10
    runs_per_day: int = 1
    cloud: str = "aws_emr"  # "aws_emr" | "databricks" | "gcp_dataproc" | "azure_synapse"
    is_spot: bool = False
    instance_type: str = "m6g.xlarge"


# Result types (unchanged public shape — backward compatible)

@dataclass
class CostBreakdown:
    rule_id: str
    severity: str
    base_cost_usd: float          # monthly $ for this rule at reference scale
    scaled_cost_usd: float        # monthly $ for this rule at the real workload
    description: str
    cloud_resource: str
    occurrences: int = 1


@dataclass
class CostEstimate:
    target: str
    workload: WorkloadProfile
    total_monthly_usd: float
    total_yearly_usd: float
    breakdown: list[CostBreakdown] = field(default_factory=list)
    by_resource: dict[str, float] = field(default_factory=dict)

    def summary_text(self) -> str:
        return (
            f"Estimated waste: ${self.total_monthly_usd:,.0f}/month "
            f"(${self.total_yearly_usd:,.0f}/year) on {self.workload.cloud}"
        )


# Estimator

class CostEstimator:
    """Estimate monthly/yearly cloud cost of PySpark anti-patterns via FinOps.

        cost = wasted_hours × monthly_runs × cluster_hourly_cost

    where ``wasted_hours`` derives from each rule's algorithmic time model and
    ``cluster_hourly_cost`` from real per-instance pricing.
    """

    def estimate(
        self,
        report: AnalysisReport,
        workload: WorkloadProfile | None = None,
    ) -> CostEstimate:
        workload = workload or WorkloadProfile()

        # --- Step 2 (once): real hourly cost of the whole cluster ---
        cluster_hourly_cost = self._cluster_hourly_cost(workload)
        monthly_runs = workload.runs_per_day * 30.5

        # Reference cluster cost, for the per-rule "base" (reference) figure.
        ref_hourly_cost = self._cluster_hourly_cost(
            WorkloadProfile(instance_type=workload.instance_type, cloud=workload.cloud)
        )
        ref_monthly_runs = 1 * 30.5

        breakdown: list[CostBreakdown] = []
        by_resource: dict[str, float] = {}

        rule_counts: dict[str, int] = {}
        for issue in report.active_issues:
            rule_counts[issue.rule_id] = rule_counts.get(issue.rule_id, 0) + 1

        seen: set[str] = set()
        for issue in report.active_issues:
            model = _COST_MODELS.get(issue.rule_id)
            if not model or issue.rule_id in seen:
                continue
            seen.add(issue.rule_id)
            occurrences = rule_counts.get(issue.rule_id, 1)

            # --- Step 1: wasted minutes per run ---
            base_minutes = self._complexity_minutes(model, workload.daily_data_tb)
            wasted_minutes = (
                base_minutes
                * _severity_multiplier(issue.severity)
                * _occurrence_factor(occurrences)
            )

            # --- Step 3: minutes → money ---
            wasted_hours = wasted_minutes / 60.0
            scaled = wasted_hours * monthly_runs * cluster_hourly_cost

            # Reference-scale figure (1 TB/day, 1 run) for comparison in reports.
            ref_minutes = (
                model.baseline_wasted_minutes
                * _severity_multiplier(issue.severity)
                * _occurrence_factor(occurrences)
            )
            base = (ref_minutes / 60.0) * ref_monthly_runs * ref_hourly_cost

            breakdown.append(
                CostBreakdown(
                    rule_id=issue.rule_id,
                    severity=issue.severity.value,
                    base_cost_usd=round(base, 2),
                    scaled_cost_usd=round(scaled, 2),
                    description=model.factor_description,
                    cloud_resource=model.category,
                    occurrences=occurrences,
                )
            )
            by_resource[model.category] = by_resource.get(model.category, 0.0) + scaled

        total_monthly = sum(b.scaled_cost_usd for b in breakdown)
        breakdown.sort(key=lambda b: -b.scaled_cost_usd)

        return CostEstimate(
            target=report.target,
            workload=workload,
            total_monthly_usd=round(total_monthly, 2),
            total_yearly_usd=round(total_monthly * 12, 2),
            breakdown=breakdown,
            by_resource={k: round(v, 2) for k, v in by_resource.items()},
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _complexity_minutes(model: AlgorithmicCostModel, data_tb: float) -> float:
        """Wasted minutes for one run at ``data_tb``, per the rule's complexity."""
        b = model.baseline_wasted_minutes
        # Guard against zero/negative volumes.
        n = max(data_tb, 0.0)
        if model.complexity is ComplexityType.FIXED:
            return b
        if model.complexity is ComplexityType.LINEAR:
            return b * n
        if model.complexity is ComplexityType.QUADRATIC:
            return b * (n ** 2)
        if model.complexity is ComplexityType.SHUFFLE_BOUND:
            return b * n * math.log2(n + 1)
        return b

    @staticmethod
    def _cluster_hourly_cost(workload: WorkloadProfile) -> float:
        """Real $/hour for the whole cluster (Step 2 of the formula)."""
        instance_price = CloudPricingFetcher.get_instance_price(
            workload.cloud, workload.instance_type
        )
        cost = instance_price * workload.cluster_nodes
        if workload.cloud.lower().startswith("databricks"):
            cost += CloudPricingFetcher.dbu_price() * workload.cluster_nodes
        if workload.is_spot:
            cost *= 0.35  # spot/preemptible ≈ 65% discount
        return cost


def _severity_multiplier(sev: Severity) -> float:
    return {
        Severity.CRITICAL: 1.5,
        Severity.HIGH: 1.0,
        Severity.MEDIUM: 0.6,
        Severity.LOW: 0.3,
        Severity.INFO: 0.1,
    }.get(sev, 1.0)


def _occurrence_factor(n: int) -> float:
    """Sub-linear scaling for multiple occurrences (caching amortizes some cost)."""
    if n <= 1:
        return 1.0
    if n <= 5:
        return 1.0 + (n - 1) * 0.5
    return 3.0 + (n - 5) * 0.2  # cap growth
