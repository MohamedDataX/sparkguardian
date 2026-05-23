"""Regex + tree-based execution plan parser."""
from __future__ import annotations

from sparkguardian.models.execution_node import ExecutionNode, NodeType
from sparkguardian.parser.node_extractors import extract_nodes


class ExecutionPlanParser:
    def parse(self, plan_text: str) -> list[ExecutionNode]:
        flat = extract_nodes(plan_text)
        return flat

    def count_node_type(self, nodes: list[ExecutionNode], node_type: NodeType) -> int:
        return sum(1 for n in nodes if n.node_type == node_type)

    def has_node_type(self, nodes: list[ExecutionNode], node_type: NodeType) -> bool:
        return any(n.node_type == node_type for n in nodes)

    def shuffle_count(self, nodes: list[ExecutionNode]) -> int:
        return sum(
            1 for n in nodes
            if n.node_type in (NodeType.EXCHANGE, NodeType.SHUFFLE_EXCHANGE)
        )
