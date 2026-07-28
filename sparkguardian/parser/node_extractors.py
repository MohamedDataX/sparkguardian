"""Extract ExecutionNode objects from the text of a Spark plan.

There is no public API to walk a physical plan from outside the JVM, so we work
off what ``df.explain()`` prints. That means matching node names with regexes.
Not bulletproof, but these names have been stable across Spark 3.x and they are
what actually shows up in real plans.
"""
from __future__ import annotations

import re

from sparkguardian.models.execution_node import ExecutionNode, NodeType

# Order matters: first pattern that matches wins. The specific names have to come
# before the generic ones, otherwise "ShuffleExchange" gets swallowed by the
# plain "Exchange" pattern and we lose the distinction.
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
    # Spark indents each nesting level by 3 characters and prefixes children with
    # "+-" or ":-". Strip those, divide by 3, and you get the depth in the tree.
    return (len(line) - len(line.lstrip("+- \t"))) // 3


def extract_nodes(plan_text: str) -> list[ExecutionNode]:
    """Parse explain() output into a flat list of nodes, in plan order.

    Flat rather than a real tree: every node carries its depth and no rule has
    needed parent/child links yet. Building the tree can wait until one does.
    """
    nodes: list[ExecutionNode] = []
    for raw_line in plan_text.splitlines():
        stripped = raw_line.strip()
        # Blank lines and "== Physical Plan ==" style headers carry no node.
        if not stripped or stripped.startswith("=="):
            continue
        node_type = _classify_line(stripped)
        depth = _get_depth(raw_line)
        nodes.append(ExecutionNode(node_type=node_type, raw_text=stripped, depth=depth))
    return nodes
