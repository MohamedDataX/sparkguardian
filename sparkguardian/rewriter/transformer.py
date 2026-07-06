"""LibCST transformers for safe source rewrites."""
from __future__ import annotations

import libcst as cst


class Repartition1ToCoalesce(cst.CSTTransformer):
    """Replace repartition(1) → coalesce(1)."""

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if not isinstance(updated_node.func, cst.Attribute):
            return updated_node
        if updated_node.func.attr.value != "repartition":
            return updated_node
        if not updated_node.args:
            return updated_node
        first = updated_node.args[0].value
        if isinstance(first, cst.Integer) and first.value == "1":
            new_attr = updated_node.func.with_changes(
                attr=cst.Name("coalesce")
            )
            return updated_node.with_changes(func=new_attr)
        return updated_node
