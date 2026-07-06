"""Dynamic rules operating on execution plan analysis results."""
from __future__ import annotations

from sparkguardian.models.execution_node import ExecutionNode, NodeType
from sparkguardian.models.issue import ImpactType, Issue, Location, Severity


def check_cartesian_product(nodes: list[ExecutionNode], source: str) -> list[Issue]:
    issues = []
    for node in nodes:
        for n in node.all_nodes():
            if n.node_type == NodeType.CARTESIAN_PRODUCT:
                issues.append(
                    Issue(
                        rule_id="CY050",
                        title="CartesianProduct detected in execution plan",
                        category="cost",
                        severity=Severity.CRITICAL,
                        impact_type=ImpactType.COST,
                        message="CartesianProduct node found — O(N*M) data explosion risk.",
                        location=Location(file=source, line=0, column=0),
                        suggestion="Add explicit join condition. Use broadcast() for small tables.",
                        explanation=(
                            "CartesianProduct creates every pair of rows from both datasets. "
                            "Grows quadratically. Almost always a bug."
                        ),
                    )
                )
    return issues


def check_excessive_shuffles(nodes: list[ExecutionNode], source: str, threshold: int = 3) -> list[Issue]:
    issues = []
    shuffle_nodes = [
        n
        for root in nodes
        for n in root.all_nodes()
        if n.is_shuffle()
    ]
    if len(shuffle_nodes) > threshold:
        issues.append(
            Issue(
                rule_id="CY051",
                title=f"Excessive shuffles: {len(shuffle_nodes)} Exchange nodes",
                category="cost",
                severity=Severity.HIGH,
                impact_type=ImpactType.COST,
                message=f"{len(shuffle_nodes)} Exchange/ShuffleExchange nodes detected.",
                location=Location(file=source, line=0, column=0),
                suggestion="Reduce wide transformations, use bucketing, AQE, or cache intermediate results.",
            )
        )
    return issues


def check_missing_broadcast(nodes: list[ExecutionNode], source: str) -> list[Issue]:
    issues = []
    for root in nodes:
        for n in root.all_nodes():
            if n.node_type == NodeType.SORT_MERGE_JOIN:
                issues.append(
                    Issue(
                        rule_id="CY052",
                        title="SortMergeJoin — possible broadcast opportunity",
                        category="cost",
                        severity=Severity.MEDIUM,
                        impact_type=ImpactType.COST,
                        message="SortMergeJoin found. If one side is small, broadcast() can eliminate shuffle.",
                        location=Location(file=source, line=0, column=0),
                        suggestion="Wrap small DataFrame with broadcast(). Check spark.sql.autoBroadcastJoinThreshold.",
                    )
                )
    return issues


def check_window_without_partition(nodes: list[ExecutionNode], source: str) -> list[Issue]:
    """Window function without partitionBy triggers global sort + single-node processing."""
    issues = []
    all_nodes = [n for root in nodes for n in root.all_nodes()]
    window_nodes = [n for n in all_nodes if n.node_type == NodeType.WINDOW]
    exchange_after_window = any(
        n.is_shuffle() for n in all_nodes
    )
    for wn in window_nodes:
        if not exchange_after_window and "partitionBy" not in wn.raw_text:
            issues.append(
                Issue(
                    rule_id="CY053",
                    title="Window function without partitionBy — potential single-partition processing",
                    category="cost",
                    severity=Severity.HIGH,
                    impact_type=ImpactType.COST,
                    message="Window node detected without evident partitioning — may force single-executor execution.",
                    location=Location(file=source, line=0, column=0),
                    suggestion="Always specify partitionBy() in window spec to distribute processing.",
                )
            )
    return issues


def check_adaptive_disabled(nodes: list[ExecutionNode], source: str) -> list[Issue]:
    """Detect plan without AdaptiveSparkPlan — AQE likely disabled."""
    all_nodes = [n for root in nodes for n in root.all_nodes()]
    has_aqe = any(n.node_type == NodeType.ADAPTIVE_SPARK_PLAN for n in all_nodes)
    shuffle_count = sum(1 for n in all_nodes if n.is_shuffle())

    if not has_aqe and shuffle_count >= 2:
        return [
            Issue(
                rule_id="CY054",
                title="AQE (Adaptive Query Execution) not active",
                category="performance",
                severity=Severity.MEDIUM,
                impact_type=ImpactType.COST,
                message="No AdaptiveSparkPlan node found with shuffles present. AQE may be disabled.",
                location=Location(file=source, line=0, column=0),
                suggestion="Enable AQE: spark.conf.set('spark.sql.adaptive.enabled', 'true')",
            )
        ]
    return []
