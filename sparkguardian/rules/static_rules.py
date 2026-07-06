"""Static AST-based PySpark anti-pattern rules."""
from __future__ import annotations

import libcst as cst
import libcst.metadata as meta

from sparkguardian.models.issue import ImpactType, Issue, Severity
from sparkguardian.rules.base import BaseRule
from sparkguardian.rules.categories import Category
from sparkguardian.rules.registry import RuleRegistry


def _get_position(node: cst.CSTNode, wrapper: meta.MetadataWrapper) -> tuple[int, int]:
    try:
        pos = wrapper.resolve(meta.PositionProvider)[node]
        return pos.start.line, pos.start.column
    except Exception:
        return 0, 0


class _MethodCallVisitor(cst.CSTVisitor):
    """Collect all method call nodes matching target method names."""

    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self, method_names: set[str]) -> None:
        self.method_names = method_names
        self.findings: list[tuple[cst.Call, int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute):
            name = node.func.attr.value
            if name in self.method_names:
                self.findings.append((node, 0, 0))


class _PositionMethodCallVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self, method_names: set[str]) -> None:
        self.method_names = method_names
        self.findings: list[tuple[str, int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute):
            name = node.func.attr.value
            if name in self.method_names:
                try:
                    pos = self.get_metadata(meta.PositionProvider, node)
                    self.findings.append((name, pos.start.line, pos.start.column))
                except Exception:
                    self.findings.append((name, 0, 0))


def _find_method_calls(
    tree: cst.Module, method_names: set[str]
) -> list[tuple[str, int, int]]:
    wrapper = meta.MetadataWrapper(tree)
    visitor = _PositionMethodCallVisitor(method_names)
    wrapper.visit(visitor)
    return visitor.findings


@RuleRegistry.register
class CollectAbuse(BaseRule):
    rule_id = "CY001"
    title = ".collect() detected — driver memory risk"
    category = Category.RELIABILITY
    severity = Severity.HIGH
    impact_type = ImpactType.RELIABILITY
    explanation = (
        ".collect() pulls entire RDD/DataFrame into driver memory. "
        "Can cause OOM on large datasets."
    )
    suggestion = "Use .take(n), .limit(n), or write to storage instead."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        issues = []
        for name, line, col in _find_method_calls(tree, {"collect"}):
            issues.append(self._make_issue(filepath, line, col, f".{name}() found"))
        return issues


@RuleRegistry.register
class ToPandasAbuse(BaseRule):
    rule_id = "CY002"
    title = ".toPandas() detected — large local materialization"
    category = Category.RELIABILITY
    severity = Severity.HIGH
    impact_type = ImpactType.RELIABILITY
    explanation = ".toPandas() collects full DataFrame to driver as Pandas. OOM risk."
    suggestion = "Use pandas-on-Spark (pyspark.pandas) or sample first."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        issues = []
        for name, line, col in _find_method_calls(tree, {"toPandas"}):
            issues.append(self._make_issue(filepath, line, col, f".{name}() found"))
        return issues


@RuleRegistry.register
class CountAbuse(BaseRule):
    rule_id = "CY003"
    title = ".count() abuse detected"
    category = Category.RELIABILITY
    severity = Severity.MEDIUM
    impact_type = ImpactType.COST
    explanation = ".count() triggers full scan and shuffle."
    suggestion = "Cache before multiple .count() calls, or use approximate counts."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        issues = []
        for _name, line, col in _find_method_calls(tree, {"count"}):
            issues.append(self._make_issue(filepath, line, col, ".count() triggers full scan"))
        return issues


class _SparkActionInLoopVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    SPARK_ACTIONS = {"collect", "toPandas", "count", "show", "take", "first", "saveAsTextFile"}
    LOOP_TYPES = (cst.For, cst.While)

    def __init__(self) -> None:
        self.findings: list[tuple[str, int, int]] = []
        self._in_loop_depth = 0

    def visit_For(self, node: cst.For) -> None:
        self._in_loop_depth += 1

    def leave_For(self, node: cst.For) -> None:
        self._in_loop_depth -= 1

    def visit_While(self, node: cst.While) -> None:
        self._in_loop_depth += 1

    def leave_While(self, node: cst.While) -> None:
        self._in_loop_depth -= 1

    def visit_Call(self, node: cst.Call) -> None:
        if self._in_loop_depth > 0 and isinstance(node.func, cst.Attribute):
            name = node.func.attr.value
            if name in self.SPARK_ACTIONS:
                try:
                    pos = self.get_metadata(meta.PositionProvider, node)
                    self.findings.append((name, pos.start.line, pos.start.column))
                except Exception:
                    self.findings.append((name, 0, 0))


@RuleRegistry.register
class SparkActionInLoop(BaseRule):
    rule_id = "CY004"
    title = "Spark action inside loop"
    category = Category.RELIABILITY
    severity = Severity.CRITICAL
    impact_type = ImpactType.RELIABILITY
    explanation = "Calling Spark actions inside loops creates new jobs per iteration. Exponential cost."
    suggestion = "Move Spark actions outside loops. Batch with unionAll or collect once."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _SparkActionInLoopVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, f".{name}() inside loop")
            for name, line, col in visitor.findings
        ]


class _RepartitionVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value != "repartition":
            return
        if not node.args:
            return
        first_arg = node.args[0].value
        if isinstance(first_arg, cst.Integer) and first_arg.value == "1":
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((1, pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((1, 0, 0))


@RuleRegistry.register
class Repartition1(BaseRule):
    rule_id = "CY008"
    title = "repartition(1) detected"
    category = Category.COST
    severity = Severity.HIGH
    impact_type = ImpactType.COST
    explanation = "repartition(1) forces full shuffle into single partition. Kills parallelism."
    suggestion = "Use coalesce(1) if reducing partitions. Only use repartition(1) before single-file export."
    autofix_available = True

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _RepartitionVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "repartition(1) forces full shuffle")
            for _, line, col in visitor.findings
        ]


class _ChainedWithColumnVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.chains: list[tuple[cst.Call, int, int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value != "withColumn":
            return
        chain_len = 1
        inner = node.func.value
        while isinstance(inner, cst.Call) and isinstance(inner.func, cst.Attribute):
            if inner.func.attr.value == "withColumn":
                chain_len += 1
                inner = inner.func.value
            else:
                break
        if chain_len >= 5:
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.chains.append((node, chain_len, pos.start.line, pos.start.column))
            except Exception:
                self.chains.append((node, chain_len, 0, 0))


@RuleRegistry.register
class ChainedWithColumn(BaseRule):
    rule_id = "CY009"
    title = "Chained withColumn() (5+) detected"
    category = Category.COST
    severity = Severity.MEDIUM
    impact_type = ImpactType.COST
    explanation = "Each withColumn() creates new DataFrame internally. Chaining 5+ is costly."
    suggestion = "Use a single select() with multiple column expressions instead."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _ChainedWithColumnVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(
                filepath, line, col, f"withColumn chain length={chain_len}"
            )
            for _, chain_len, line, col in visitor.chains
        ]


class _ImplicitJoinVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value != "join":
            return
        has_how = any(
            (isinstance(arg.keyword, cst.Name) and arg.keyword.value == "how")
            or (isinstance(arg.keyword, cst.Name) and arg.keyword.value == "on")
            for arg in node.args
            if arg.keyword is not None
        )
        positional_count = sum(1 for a in node.args if a.keyword is None)
        if positional_count < 3 and not has_how:
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))


@RuleRegistry.register
class ImplicitJoin(BaseRule):
    rule_id = "CY010"
    title = "Implicit join without how= parameter"
    category = Category.CLARITY
    severity = Severity.LOW
    impact_type = ImpactType.CLARITY
    explanation = "Join without explicit how= defaults to inner join silently."
    suggestion = "Always specify how='inner'|'left'|'right'|'outer' for clarity."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _ImplicitJoinVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "join() missing how= parameter")
            for line, col in visitor.findings
        ]


class _SelectStarVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value != "select":
            return
        for arg in node.args:
            if isinstance(arg.value, cst.SimpleString) and arg.value.value in ('"*"', "'*'"):
                try:
                    pos = self.get_metadata(meta.PositionProvider, node)
                    self.findings.append((pos.start.line, pos.start.column))
                except Exception:
                    self.findings.append((0, 0))
                break


@RuleRegistry.register
class SelectStar(BaseRule):
    rule_id = "CY011"
    title = 'select("*") — broad column selection'
    category = Category.CLARITY
    severity = Severity.LOW
    impact_type = ImpactType.CLARITY
    explanation = 'select("*") reads all columns including unneeded ones. Increases I/O.'
    suggestion = "Explicitly name required columns in select()."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _SelectStarVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, 'select("*") — explicit columns preferred')
            for line, col in visitor.findings
        ]


class _PythonUDFVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        is_udf = (
            isinstance(node.func, cst.Attribute) and node.func.attr.value == "udf"
        ) or (
            isinstance(node.func, cst.Name) and node.func.value == "udf"
        )
        if is_udf:
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))

    def visit_Decorator(self, node: cst.Decorator) -> None:
        if isinstance(node.decorator, cst.Attribute) and node.decorator.attr.value == "udf":
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))
        elif isinstance(node.decorator, cst.Name) and node.decorator.value == "udf":
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))


@RuleRegistry.register
class PythonUDFUsage(BaseRule):
    rule_id = "CY020"
    title = "Python UDF detected — prefer native Spark SQL functions"
    category = Category.UDF
    severity = Severity.HIGH
    impact_type = ImpactType.COST
    explanation = (
        "Python UDFs bypass JVM optimization: row-by-row serialization, "
        "no Catalyst optimizer, no tungsten encoding."
    )
    suggestion = (
        "Use native pyspark.sql.functions, SQL expressions, or pandas_udf (vectorized)."
    )
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _PythonUDFVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "Python UDF bypasses JVM/Catalyst")
            for line, col in visitor.findings
        ]


class _ShowCallVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute) and node.func.attr.value == "show":
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))


@RuleRegistry.register
class ShowInProduction(BaseRule):
    rule_id = "CY005"
    title = ".show() in production code"
    category = Category.RELIABILITY
    severity = Severity.LOW
    impact_type = ImpactType.RELIABILITY
    explanation = ".show() triggers an action and prints to stdout. Not suitable for production jobs."
    suggestion = "Remove .show() calls from production pipelines. Use logging or write outputs."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _ShowCallVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, ".show() in production code")
            for line, col in visitor.findings
        ]


# ---------------------------------------------------------------------------
# CY012 — Excessive cache()/persist() calls
# ---------------------------------------------------------------------------

class _CacheCallVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[str, int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute):
            name = node.func.attr.value
            if name in ("cache", "persist"):
                try:
                    pos = self.get_metadata(meta.PositionProvider, node)
                    self.findings.append((name, pos.start.line, pos.start.column))
                except Exception:
                    self.findings.append((name, 0, 0))


@RuleRegistry.register
class ExcessiveCache(BaseRule):
    rule_id = "CY012"
    title = "cache()/persist() detected — verify necessity"
    category = Category.COST
    severity = Severity.LOW
    impact_type = ImpactType.COST
    explanation = (
        "Caching consumes executor memory. Over-caching evicts other cached data "
        "or spills to disk. Only cache DataFrames reused 2+ times."
    )
    suggestion = "Cache only DataFrames used multiple times. Call df.unpersist() when done."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _CacheCallVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, f".{name}() — verify reuse justifies caching")
            for name, line, col in visitor.findings
        ]


# ---------------------------------------------------------------------------
# CY013 — Repeated scans (same DataFrame created from same source 2+ times)
# ---------------------------------------------------------------------------

class _ReadCallVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self._read_paths: list[tuple[str, int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value not in ("parquet", "csv", "json", "orc", "text"):
            return
        if not node.args:
            return
        path_arg = node.args[0].value
        if isinstance(path_arg, cst.SimpleString):
            path_val = path_arg.evaluated_value
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self._read_paths.append((str(path_val), pos.start.line, pos.start.column))
            except Exception:
                self._read_paths.append((str(path_val), 0, 0))

    def duplicates(self) -> list[tuple[str, int, int]]:
        seen: dict[str, int] = {}
        dupes: list[tuple[str, int, int]] = []
        for path, line, col in self._read_paths:
            if path in seen:
                dupes.append((path, line, col))
            else:
                seen[path] = line
        return dupes


@RuleRegistry.register
class RepeatedScan(BaseRule):
    rule_id = "CY013"
    title = "Repeated scan of same data source"
    category = Category.COST
    severity = Severity.HIGH
    impact_type = ImpactType.COST
    explanation = "Reading same source twice = double I/O + double parsing."
    suggestion = "Read once into a DataFrame, cache() if reused multiple times."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _ReadCallVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, f"Repeated scan: '{path}'")
            for path, line, col in visitor.duplicates()
        ]


# ---------------------------------------------------------------------------
# CY014 — groupBy before filter (should filter first)
# ---------------------------------------------------------------------------

class _GroupByBeforeFilterVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value != "filter":
            return
        inner = node.func.value
        while isinstance(inner, cst.Call) and isinstance(inner.func, cst.Attribute):
            if inner.func.attr.value == "groupBy":
                try:
                    pos = self.get_metadata(meta.PositionProvider, node)
                    self.findings.append((pos.start.line, pos.start.column))
                except Exception:
                    self.findings.append((0, 0))
                break
            inner = inner.func.value


@RuleRegistry.register
class GroupByBeforeFilter(BaseRule):
    rule_id = "CY014"
    title = "filter() after groupBy() — filter should come first"
    category = Category.COST
    severity = Severity.MEDIUM
    impact_type = ImpactType.COST
    explanation = "filter() after groupBy() processes all rows before reduction. Reorder to filter first."
    suggestion = "Move filter() before groupBy() to reduce shuffle input size."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _GroupByBeforeFilterVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "filter() after groupBy() — reorder to filter first")
            for line, col in visitor.findings
        ]


# ---------------------------------------------------------------------------
# CY016 — crossJoin() explicit detection
# ---------------------------------------------------------------------------

class _CrossJoinVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute) and node.func.attr.value == "crossJoin":
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))


@RuleRegistry.register
class CrossJoin(BaseRule):
    rule_id = "CY016"
    title = "crossJoin() — explicit CartesianProduct"
    category = Category.COST
    severity = Severity.HIGH
    impact_type = ImpactType.COST
    explanation = "crossJoin() creates CartesianProduct: O(N*M) rows. Explosive for large tables."
    suggestion = "Only use crossJoin() on tiny tables (< 10K rows). Add immediate filter() after."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _CrossJoinVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "crossJoin() — CartesianProduct risk")
            for line, col in visitor.findings
        ]


# ---------------------------------------------------------------------------
# CY017 — Multiple distinct() calls
# ---------------------------------------------------------------------------

class _DistinctVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute) and node.func.attr.value == "distinct":
            try:
                pos = self.get_metadata(meta.PositionProvider, node)
                self.findings.append((pos.start.line, pos.start.column))
            except Exception:
                self.findings.append((0, 0))


@RuleRegistry.register
class DistinctAbuse(BaseRule):
    rule_id = "CY017"
    title = "distinct() detected — triggers full shuffle"
    category = Category.COST
    severity = Severity.MEDIUM
    impact_type = ImpactType.COST
    explanation = "distinct() requires a full shuffle to deduplicate across partitions."
    suggestion = "Use dropDuplicates(subset_cols) to deduplicate on specific columns only."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _DistinctVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "distinct() forces full shuffle")
            for line, col in visitor.findings
        ]


# ---------------------------------------------------------------------------
# CY018 — orderBy/sort without limit
# ---------------------------------------------------------------------------

class _OrderByWithoutLimitVisitor(cst.CSTVisitor):
    """
    df.orderBy(...).limit(N) in CST:
      Call(func=Attribute(value=Call(orderBy), attr="limit"))
    The limit Call is visited first (pre-order). We mark the inner orderBy node
    as safe, then flag any orderBy not in the safe set.
    """
    METADATA_DEPENDENCIES = (meta.PositionProvider,)

    def __init__(self) -> None:
        self.findings: list[tuple[int, int]] = []
        self._safe_ids: set[int] = set()

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Attribute) and node.func.attr.value == "limit":
            inner = node.func.value
            if isinstance(inner, cst.Call) and isinstance(inner.func, cst.Attribute):
                if inner.func.attr.value in ("orderBy", "sort"):
                    self._safe_ids.add(id(inner))

        if not isinstance(node.func, cst.Attribute):
            return
        if node.func.attr.value not in ("orderBy", "sort"):
            return
        if id(node) in self._safe_ids:
            return
        try:
            pos = self.get_metadata(meta.PositionProvider, node)
            self.findings.append((pos.start.line, pos.start.column))
        except Exception:
            self.findings.append((0, 0))


@RuleRegistry.register
class OrderByWithoutLimit(BaseRule):
    rule_id = "CY018"
    title = "orderBy()/sort() without limit() — global sort"
    category = Category.COST
    severity = Severity.MEDIUM
    impact_type = ImpactType.COST
    explanation = "Global sort without limit triggers full shuffle + O(N log N) sort across all partitions."
    suggestion = "Use df.orderBy(...).limit(N) for top-N. Use sortWithinPartitions() for local sort."
    autofix_available = False

    def check(self, tree: cst.Module, filepath: str) -> list[Issue]:
        wrapper = meta.MetadataWrapper(tree)
        visitor = _OrderByWithoutLimitVisitor()
        wrapper.visit(visitor)
        return [
            self._make_issue(filepath, line, col, "orderBy() without limit() — global O(N log N) sort")
            for line, col in visitor.findings
        ]
