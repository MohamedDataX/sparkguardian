"""Cost Estimator — translates anti-patterns into estimated cloud cost impact.

Methodology:
  Each rule has a cost model derived from AWS EMR / Databricks / Glue pricing
  and Spark performance research. Estimates are conservative lower bounds for
  a "medium" workload (1 TB/day, 10-node cluster, on-demand pricing).

Pricing sources (2025-2026):
  - AWS EMR on-demand: ~$0.063/vCPU-hour (m6g.xlarge)
  - Databricks DBU: $0.40/DBU-hour (Jobs Compute)
  - AWS S3: $0.023/GB stored + $0.005/1k GET requests
  - Network egress: $0.09/GB cross-AZ
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sparkguardian.models.issue import Severity
from sparkguardian.models.report import AnalysisReport


@dataclass
class CostModel:
    """Cost model per rule — monthly USD impact for medium workload."""
    rule_id: str
    monthly_usd: float
    factor_description: str
    cloud_resource: str  # "compute" | "storage" | "network" | "io"



# Cost models — conservative estimates for medium workload (1 TB/day, 10 nodes)


_COST_MODELS: dict[str, CostModel] = {
    # Reliability — driver OOM = job crash = pipeline rerun
    "CY001": CostModel(
        rule_id="CY001",
        monthly_usd=120.0,
        factor_description="Job rerun cost when driver OOMs (1-2 failures/month)",
        cloud_resource="compute",
    ),
    "CY002": CostModel(
        rule_id="CY002",
        monthly_usd=180.0,
        factor_description="Driver upgrade + rerun cost (toPandas OOMs frequent)",
        cloud_resource="compute",
    ),
    "CY003": CostModel(
        rule_id="CY003",
        monthly_usd=45.0,
        factor_description="Repeated full table scans (~3x extra reads/day)",
        cloud_resource="io",
    ),

    # CRITICAL — Spark action in loop = exponential job multiplication
    "CY004": CostModel(
        rule_id="CY004",
        monthly_usd=850.0,
        factor_description="N jobs vs 1 job — typically 10-100x compute overhead",
        cloud_resource="compute",
    ),

    "CY005": CostModel(
        rule_id="CY005",
        monthly_usd=15.0,
        factor_description="Stdout overhead + extra action triggers",
        cloud_resource="compute",
    ),

    # Cost — shuffle is the #1 expense in Spark
    "CY008": CostModel(
        rule_id="CY008",
        monthly_usd=320.0,
        factor_description="Full shuffle + single-partition bottleneck (~3x runtime)",
        cloud_resource="compute",
    ),
    "CY009": CostModel(
        rule_id="CY009",
        monthly_usd=65.0,
        factor_description="Deep plan tree degrades Catalyst (~15% planning overhead)",
        cloud_resource="compute",
    ),
    "CY010": CostModel(
        rule_id="CY010",
        monthly_usd=25.0,
        factor_description="Implicit inner join — silent data loss costs analyst time",
        cloud_resource="compute",
    ),
    "CY011": CostModel(
        rule_id="CY011",
        monthly_usd=180.0,
        factor_description="No column pruning — ~70% extra I/O on Parquet/ORC",
        cloud_resource="io",
    ),
    "CY012": CostModel(
        rule_id="CY012",
        monthly_usd=40.0,
        factor_description="Wasted storage memory + LRU eviction overhead",
        cloud_resource="compute",
    ),
    "CY013": CostModel(
        rule_id="CY013",
        monthly_usd=210.0,
        factor_description="Duplicate I/O + S3 API costs (~2x scan cost)",
        cloud_resource="io",
    ),
    "CY014": CostModel(
        rule_id="CY014",
        monthly_usd=95.0,
        factor_description="Larger shuffle input (~5x post-aggregation rows)",
        cloud_resource="compute",
    ),
    "CY016": CostModel(
        rule_id="CY016",
        monthly_usd=480.0,
        factor_description="N*M row explosion — runtime can grow 100x+",
        cloud_resource="compute",
    ),
    "CY017": CostModel(
        rule_id="CY017",
        monthly_usd=110.0,
        factor_description="Full shuffle for deduplication (~30% extra runtime)",
        cloud_resource="compute",
    ),
    "CY018": CostModel(
        rule_id="CY018",
        monthly_usd=140.0,
        factor_description="O(N log N) global sort vs O(N) top-N (~5x runtime)",
        cloud_resource="compute",
    ),
    "CY020": CostModel(
        rule_id="CY020",
        monthly_usd=380.0,
        factor_description="Python UDF 10-100x slower than native — typically 20x overhead",
        cloud_resource="compute",
    ),

    # Dynamic rules — plan-level issues
    "CY050": CostModel(
        rule_id="CY050",
        monthly_usd=950.0,
        factor_description="CartesianProduct — N*M rows can crash cluster",
        cloud_resource="compute",
    ),
    "CY051": CostModel(
        rule_id="CY051",
        monthly_usd=290.0,
        factor_description="Excessive shuffles — disk I/O + network egress costs",
        cloud_resource="network",
    ),
    "CY052": CostModel(
        rule_id="CY052",
        monthly_usd=160.0,
        factor_description="Missed broadcast = sort+shuffle both sides (~3x cost)",
        cloud_resource="compute",
    ),
    "CY053": CostModel(
        rule_id="CY053",
        monthly_usd=220.0,
        factor_description="Single-partition window — N-way parallelism lost",
        cloud_resource="compute",
    ),
    "CY054": CostModel(
        rule_id="CY054",
        monthly_usd=200.0,
        factor_description="No AQE — static plan with skew/over-partitioning waste",
        cloud_resource="compute",
    ),
}


# Workload scaling factors


@dataclass
class WorkloadProfile:
    """Workload scale relative to baseline (1 TB/day, 10 nodes, daily run)."""
    daily_data_tb: float = 1.0
    cluster_nodes: int = 10
    runs_per_day: int = 1
    cloud: str = "aws_emr"  # "aws_emr" | "databricks" | "gcp_dataproc" | "azure_synapse"

    @property
    def scale_factor(self) -> float:
        """Multiplier vs baseline workload."""
        data_factor = self.daily_data_tb / 1.0
        cluster_factor = self.cluster_nodes / 10.0
        run_factor = self.runs_per_day / 1.0
        return data_factor * cluster_factor * run_factor

    @property
    def cloud_multiplier(self) -> float:
        """Relative cost multiplier vs AWS EMR baseline."""
        return {
            "aws_emr": 1.0,
            "databricks": 1.3,
            "gcp_dataproc": 0.9,
            "azure_synapse": 1.1,
        }.get(self.cloud, 1.0)


# ---------------------------------------------------------------------------
# Cost estimation result
# ---------------------------------------------------------------------------

@dataclass
class CostBreakdown:
    rule_id: str
    severity: str
    base_cost_usd: float
    scaled_cost_usd: float
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


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------

class CostEstimator:
    """
    Estimates monthly/yearly cloud cost impact of PySpark anti-patterns.

    Uses conservative lower-bound estimates based on:
    - AWS EMR / Databricks / GCP Dataproc on-demand pricing
    - Spark performance research (shuffle cost, UDF overhead, plan optimization)
    - Real-world incident cost (driver OOM = job rerun)

    All estimates are PER MONTH for the configured WorkloadProfile.
    """

    def estimate(
        self,
        report: AnalysisReport,
        workload: WorkloadProfile | None = None,
    ) -> CostEstimate:
        workload = workload or WorkloadProfile()
        breakdown: list[CostBreakdown] = []
        by_resource: dict[str, float] = {}

        # Count occurrences per rule
        rule_counts: dict[str, int] = {}
        for issue in report.active_issues:
            rule_counts[issue.rule_id] = rule_counts.get(issue.rule_id, 0) + 1

        scale = workload.scale_factor * workload.cloud_multiplier

        for issue in report.active_issues:
            model = _COST_MODELS.get(issue.rule_id)
            if not model:
                continue
            occurrences = rule_counts.get(issue.rule_id, 1)
            severity_multiplier = _severity_multiplier(issue.severity)
            base = model.monthly_usd * severity_multiplier
            scaled = base * scale * _occurrence_factor(occurrences)

            already_counted = any(
                b.rule_id == issue.rule_id for b in breakdown
            )
            if not already_counted:
                breakdown.append(
                    CostBreakdown(
                        rule_id=issue.rule_id,
                        severity=issue.severity.value,
                        base_cost_usd=base,
                        scaled_cost_usd=scaled,
                        description=model.factor_description,
                        cloud_resource=model.cloud_resource,
                        occurrences=occurrences,
                    )
                )
                by_resource[model.cloud_resource] = (
                    by_resource.get(model.cloud_resource, 0.0) + scaled
                )

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
