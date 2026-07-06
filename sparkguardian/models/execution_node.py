from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    EXCHANGE = "Exchange"
    SHUFFLE_EXCHANGE = "ShuffleExchange"
    HASH_AGGREGATE = "HashAggregate"
    SORT_MERGE_JOIN = "SortMergeJoin"
    BROADCAST_HASH_JOIN = "BroadcastHashJoin"
    CARTESIAN_PRODUCT = "CartesianProduct"
    ADAPTIVE_SPARK_PLAN = "AdaptiveSparkPlan"
    WINDOW = "Window"
    WHOLE_STAGE_CODEGEN = "WholeStageCodegen"
    FILTER = "Filter"
    PROJECT = "Project"
    FILE_SCAN = "FileScan"
    REPARTITION = "Repartition"
    UNKNOWN = "Unknown"


@dataclass
class ExecutionNode:
    node_type: NodeType
    raw_text: str
    depth: int = 0
    children: list[ExecutionNode] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    estimated_rows: int | None = None
    estimated_bytes: int | None = None

    def is_shuffle(self) -> bool:
        return self.node_type in (NodeType.EXCHANGE, NodeType.SHUFFLE_EXCHANGE)

    def is_join(self) -> bool:
        return self.node_type in (
            NodeType.SORT_MERGE_JOIN,
            NodeType.BROADCAST_HASH_JOIN,
            NodeType.CARTESIAN_PRODUCT,
        )

    def all_nodes(self) -> list[ExecutionNode]:
        result = [self]
        for child in self.children:
            result.extend(child.all_nodes())
        return result
