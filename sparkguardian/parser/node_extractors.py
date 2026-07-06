"""Extract ExecutionNode tree from Spark plan text."""
from __future__ import annotations

import re

from sparkguardian.models.execution_node import ExecutionNode, NodeType

_NODE_PATTERNS: list[tuple[NodeType, re.Pattern[str]]] = [
    (NodeType.CARTESIAN_PRODUCT, re.compile(r"CartesianProduct", re.I)),
    (NodeType.BROADCAST_HASH_JOIN, re.compile(r"BroadcastHashJoin", re.I)),
    (NodeType.SORT_MERGE_JOIN, re.compile(r"SortMergeJoin", re.I)),
    (NodeType.SHUFFLE_EXCHANGE, re.compile(r"ShuffleExchange", re.I)),
    (NodeType.EXCHANGE, re.compile(r"\bExchange\b", re.I)),
    (NodeType.HASH_AGGREGATE, re.compile(r"HashAggregate", re.I)),
    (NodeType.ADAPTIVE_SPARK_PLAN, re.compile(r"AdaptiveSparkPlan", re.I)),
    (NodeType.WINDOW, re.compile(r"\bWindow\b", re.I)),
    (NodeType.WHOLE_STAGE_CODEGEN, re.compile(r"WholeStageCodegen", re.I)),
    (NodeType.FILE_SCAN, re.compile(r"FileScan|Scan parquet|Scan csv|Scan json", re.I)),
    (NodeType.REPARTITION, re.compile(r"\bRepartition\b", re.I)),
    (NodeType.FILTER, re.compile(r"\bFilter\b", re.I)),
    (NodeType.PROJECT, re.compile(r"\bProject\b", re.I)),
]


def _classify_line(line: str) -> NodeType:
    for node_type, pattern in _NODE_PATTERNS:
        if pattern.search(line):
            return node_type
    return NodeType.UNKNOWN


def _get_depth(line: str) -> int:
    return (len(line) - len(line.lstrip("+- \t"))) // 3


def extract_nodes(plan_text: str) -> list[ExecutionNode]:
    """Parse Spark explain() output into flat list of ExecutionNodes."""
    nodes: list[ExecutionNode] = []
    for raw_line in plan_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("=="):
            continue
        node_type = _classify_line(stripped)
        depth = _get_depth(raw_line)
        nodes.append(ExecutionNode(node_type=node_type, raw_text=stripped, depth=depth))
    return nodes
