"""RAG — Spark knowledge base from official Apache Spark documentation.

Sources (Spark 4.1.1, fetched 2026-05-19):
  https://spark.apache.org/docs/latest/tuning.html
  https://spark.apache.org/docs/latest/sql-performance-tuning.html
  https://spark.apache.org/docs/latest/rdd-programming-guide.html
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class KnowledgeEntry:
    rule_id: str
    keywords: list[str]
    title: str
    content: str
    source_url: str = "https://spark.apache.org/docs/latest/tuning.html"
    config_params: list[str] = field(default_factory=list)


_KNOWLEDGE_BASE: list[KnowledgeEntry] = [

    KnowledgeEntry(
        rule_id="CY001",
        keywords=["collect", "driver", "oom", "memory", "heap", "action"],
        title=".collect() — full dataset materialization on driver JVM heap",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=[],
        content="""Official Spark RDD guide: "rdd.collect().foreach(println) fetches entire
RDD to driver — OOM risk." Calling collect() brings ALL data from ALL partitions
to the driver JVM heap. Java objects consume 2-5x more memory than raw data
(tuning guide: object header ~16 bytes, String ~40 bytes overhead per instance).

Safe alternatives documented in Spark:
- df.take(N) — fetches only N rows to driver
- df.write.parquet("path") — persists to storage without driver collection
- df.foreach() / df.foreachBatch() — processes data on executors, never on driver
- df.limit(N).collect() — limits exposure before collecting""",
    ),

    KnowledgeEntry(
        rule_id="CY002",
        keywords=["topandas", "pandas", "driver", "oom", "collect", "materialization"],
        title=".toPandas() — implicit collect() to driver as Pandas DataFrame",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=[],
        content="""toPandas() calls collect() internally. The Spark tuning guide documents
Java String overhead: ~60 bytes for a 10-character string (UTF-16 encoding + 40 bytes
object header). String-heavy DataFrames consume far more driver memory than raw data size.

Official alternatives:
- pyspark.pandas (Koalas API): distributed Pandas-like API, stays on executors
- df.sample(fraction=0.01).toPandas(): safe for sampling use cases
- df.write.csv() / df.write.parquet(): persist to storage instead of collecting
- spark.read.format("pandas"): read from storage in Pandas when truly needed""",
    ),

    KnowledgeEntry(
        rule_id="CY003",
        keywords=["count", "scan", "action", "trigger", "aggregate", "full", "cache"],
        title=".count() — triggers full DAG evaluation and table scan",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=["spark.sql.shuffle.partitions", "spark.sql.adaptive.enabled"],
        content="""Spark RDD guide: "by default, each transformed RDD may be recomputed each
time you run an action on it." count() is an action — it triggers full evaluation.
Multiple count() calls on the same unpersisted DataFrame = multiple full scans.

Official fixes:
- Call df.cache() before multiple count() invocations
- Approximate count: df.rdd.countApprox(timeout=1000, confidence=0.95)
- SQL alternative: spark.sql("SELECT approx_count_distinct(id) FROM table")
- AQE (spark.sql.adaptive.enabled=true, default since Spark 3.2) does NOT reduce
  count() scan cost — it only optimizes shuffle/join operations""",
    ),

    KnowledgeEntry(
        rule_id="CY004",
        keywords=["loop", "action", "job", "iteration", "foreach", "count", "collect"],
        title="Spark action in loop — N separate Spark jobs launched",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=["spark.default.parallelism"],
        content="""Spark RDD guide: "All transformations are lazy — computation happens only
when an action is called. Each action triggers a new Spark job (full DAG evaluation)."
N loop iterations x 1 action = N Spark jobs. Each job includes: DAG planning,
task scheduling, executor allocation, and full scan.

The tuning guide states Spark efficiently supports tasks as short as 200ms — the
overhead is not per-task but per-job (DAG compilation, scheduler round-trip).

Official fixes:
- Collect data once outside the loop, iterate in Python
- Batch iterations: df.groupBy("key").agg(F.sum("value")) replaces a counting loop
- Use df.filter() + single action instead of per-iteration filter + action
- Target: spark.default.parallelism = 2-3x CPU cores in cluster""",
    ),

    KnowledgeEntry(
        rule_id="CY005",
        keywords=["show", "print", "stdout", "executor", "debug", "production"],
        title=".show() in production — action + output scattered on executor stdout",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=[],
        content="""Spark RDD guide explicitly warns: "rdd.foreach(println) prints on executors,
not driver — output is scattered across worker node stdout files, not visible to operator."
show() is a Spark action (triggers full DAG evaluation) that also calls collect().
In cluster mode, output goes to executor stdout in work directories, not driver logs.

Official guidance:
- Remove show() calls from production pipelines entirely
- Use structured logging: spark.sparkContext.setLogLevel("WARN")
- Write outputs to storage: df.write.parquet() or df.write.mode("overwrite").csv()
- For debugging only: df.take(5) or df.limit(5).show() (bounded)""",
    ),

    KnowledgeEntry(
        rule_id="CY008",
        keywords=["repartition", "coalesce", "shuffle", "partition", "single", "parallelism"],
        title="repartition(1) — full shuffle collapsing all data into one partition",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=["spark.sql.shuffle.partitions"],
        content="""Spark RDD guide distinguishes the two operations:
"coalesce() decreases partition count WITHOUT a full shuffle — more efficient for
filtering down a large dataset. repartition() ALWAYS performs a full shuffle
regardless of direction of partition count change."

The guide also recommends repartitionAndSortWithinPartitions() which "pushes sorting
down into the shuffle machinery — more efficient than repartition() followed by sort()."

When repartition(1) is acceptable (official docs):
- Immediately before writing a single-file output (CSV, text) that downstream
  tools require in one file — only valid use case.

Fix: replace repartition(1) with coalesce(1). Coalesce avoids network shuffle
by merging existing partitions locally.""",
    ),

    KnowledgeEntry(
        rule_id="CY009",
        keywords=["withcolumn", "chain", "select", "schema", "catalyst", "plan", "tree"],
        title="Chained withColumn() — Catalyst logical plan tree degradation",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=[],
        content="""The SQL performance tuning guide notes that Catalyst applies rule-based and
cost-based optimization across the logical plan tree. Each withColumn() adds a new
Project node to the logical plan tree. Chaining 5+ withColumn() calls creates a
deep tree: Catalyst rule application is O(N) per rule across N plan nodes.

The in-memory columnar storage section confirms: "scans only required columns" —
this optimization works most effectively when columns are declared in a single
select() projection, not scattered across multiple withColumn() nodes.

Fix: replace chained withColumn() with a single select():
  df.select("*", expr1.alias("a"), expr2.alias("b"), expr3.alias("c"))
This produces ONE Project node in the physical plan instead of N nested nodes.""",
    ),

    KnowledgeEntry(
        rule_id="CY010",
        keywords=["join", "how", "implicit", "inner", "outer", "left", "right", "type"],
        title="Implicit join — missing how= defaults silently to inner join",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=["spark.sql.autoBroadcastJoinThreshold", "spark.sql.broadcastTimeout"],
        content="""The SQL performance tuning guide documents join strategy hints in priority order:
BROADCAST > MERGE (sort-merge) > SHUFFLE_HASH > SHUFFLE_REPLICATE_NL.
The join TYPE (inner/left/right/outer) determines plan semantics and eligible strategies.

Without how=: Spark defaults to inner join, silently dropping non-matching rows.
This causes data loss bugs that are hard to detect in production.
Additionally, outer joins cannot always use BroadcastHashJoin — the optimizer needs
the explicit join type to select the optimal strategy.

Fix: always specify how="inner"|"left"|"right"|"outer"|"left_semi"|"anti".
For broadcast: df.join(broadcast(small_df), "key", how="inner").
Threshold config: spark.sql.autoBroadcastJoinThreshold = 10MB (default).""",
    ),

    KnowledgeEntry(
        rule_id="CY011",
        keywords=["select", "star", "columns", "io", "projection", "pushdown", "parquet", "orc"],
        title="select('*') — prevents column pruning pushdown to data source",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=["spark.sql.inMemoryColumnarStorage.compressed"],
        content="""The SQL performance tuning guide on in-memory columnar storage:
"scans only required columns" — but only when required columns are explicitly specified.

For Parquet/ORC (columnar formats): select("*") forces reading ALL column chunks.
Parquet stores data column-by-column, so reading only 3 of 100 columns skips ~97% of I/O.
select("*") defeats this optimization entirely.

For in-memory caching: spark.sql.inMemoryColumnarStorage.compressed=true (default)
compresses each column individually — wider select = more columns to compress/decompress.

Fix: explicitly name only the columns your pipeline needs:
  df.select("id", "name", "timestamp", "amount")
Use df.columns or DESCRIBE table to discover available columns.""",
    ),

    KnowledgeEntry(
        rule_id="CY012",
        keywords=["cache", "persist", "memory", "storage", "eviction", "lru", "unpersist", "level"],
        title="cache()/persist() — LRU eviction pressure and memory waste",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=[
            "spark.memory.storageFraction",
            "spark.memory.fraction",
            "spark.sql.inMemoryColumnarStorage.batchSize",
        ],
        content="""Spark tuning guide memory architecture:
  M = unified memory = (JVM heap - 300MB) x spark.memory.fraction (default 0.6)
  R = storage-immune region = M x spark.memory.storageFraction (default 0.5)

Spark uses LRU eviction. Caching DataFrames that are only used once wastes R region,
evicting other cached data and increasing GC pressure.

Official storage level guidance (RDD guide):
  1. MEMORY_ONLY: most CPU-efficient — use if data fits (default for cache())
  2. MEMORY_ONLY_SER + Kryo: space-efficient, still fast — use if data is large
  3. MEMORY_AND_DISK: only if recomputation is very expensive
  4. Do NOT use disk for cheap transformations — recompute is often faster than disk read

Rules:
- Only cache DataFrames used 2+ times
- Call df.unpersist() when done to free R region
- spark.sql.inMemoryColumnarStorage.batchSize=10000 — larger improves compression, risks OOM""",
    ),

    KnowledgeEntry(
        rule_id="CY013",
        keywords=["scan", "read", "source", "repeated", "parquet", "csv", "json", "reuse", "twice"],
        title="Repeated scan — multiple full reads of same data source",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=["spark.sql.files.maxPartitionBytes"],
        content="""Spark RDD guide: "by default, each transformed RDD may be recomputed each time
you run an action on it." Reading the same source file path twice creates two separate
FileScan nodes in the physical plan — two full reads including:
  - File listing (spark.sql.files.maxPartitionBytes=128MB splits files into partitions)
  - Decompression (Parquet/Snappy: 2-3x expansion per tuning guide)
  - Deserialization into Spark internal format

For object stores (S3/GCS/Azure Blob): repeated reads also incur per-API-request costs
and per-byte egress charges.

Fix: read once, then cache() if reused multiple times:
  df = spark.read.parquet("s3://bucket/data/")
  df.cache()
  result_a = df.filter(...)
  result_b = df.groupBy(...)
  df.unpersist()""",
    ),

    KnowledgeEntry(
        rule_id="CY014",
        keywords=["groupby", "filter", "predicate", "pushdown", "catalyst", "aggregate", "having"],
        title="filter() after groupBy() — missed predicate pushdown opportunity",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=["spark.sql.adaptive.enabled"],
        content="""The SQL performance tuning guide on statistics and Catalyst CBO:
"inaccurate/missing statistics hinder optimal plan selection and degrade performance."
Catalyst applies predicate pushdown to move filter() BEFORE aggregations — but only for
filters on source columns, not on aggregated results.

filter() after groupBy() on source columns: Catalyst may not always push this down
automatically — manual reordering guarantees the optimization.

Effect: filtering BEFORE groupBy reduces shuffle input size dramatically.
Example:
  # SLOW: shuffles all rows then filters
  df.groupBy("dept").agg(F.sum("salary")).filter(F.col("dept") == "ENG")

  # FAST: filters first, shuffles only ENG rows
  df.filter(F.col("dept") == "ENG").groupBy("dept").agg(F.sum("salary"))

AQE (spark.sql.adaptive.enabled=true) helps post-shuffle but cannot reorder
pre-shuffle filter/groupBy operations.""",
    ),

    KnowledgeEntry(
        rule_id="CY016",
        keywords=["crossjoin", "cartesian", "product", "broadcast", "nl", "nested", "loop", "explicit"],
        title="crossJoin() — SHUFFLE_REPLICATE_NL join (O(N*M) row explosion)",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=["spark.sql.autoBroadcastJoinThreshold"],
        content="""SQL performance tuning guide lists join strategy hints by priority:
1. BROADCAST (hash join) — highest priority
2. MERGE (sort-merge join)
3. SHUFFLE_HASH (shuffled hash join)
4. SHUFFLE_REPLICATE_NL (nested loop join) — LOWEST priority, used for cross joins

crossJoin() forces strategy 4 regardless of table sizes. Output = N * M rows.
For 1M x 1M tables: 10^12 output rows — exhausts executor memory and disk.
Shuffle intermediate files: "preserved until GC'd — can consume large disk space."

Safe use cases (from Spark docs):
- Tiny reference tables (< 10K rows) immediately followed by a selective filter()
- Non-equi join conditions where no equi-key exists

Better alternatives:
- Add equi-join key to use BroadcastHashJoin: df.join(broadcast(small_df), "key")
- Threshold for auto-broadcast: spark.sql.autoBroadcastJoinThreshold=10MB""",
    ),

    KnowledgeEntry(
        rule_id="CY017",
        keywords=["distinct", "deduplicate", "shuffle", "hash", "sort", "aggregate", "partition"],
        title="distinct() — full shuffle for global deduplication",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=[
            "spark.sql.shuffle.partitions",
            "spark.sql.adaptive.coalescePartitions.enabled",
        ],
        content="""Spark RDD guide lists shuffle triggers: "repartition operations, ByKey operations
(except counting), join operations (cogroup, join)." distinct() internally implements
a groupBy + aggregate — it is a wide transformation requiring full data shuffle.

Tuning guide on shuffle cost: "involves disk I/O, data serialization, and network I/O.
Spark generates map tasks to organize data written to a single file, and reduce tasks to
read sorted blocks. Intermediate files preserved until RDD GC'd — can consume large
disk space in long-running jobs."

Fixes:
- dropDuplicates(["col1", "col2"]): deduplicates on a subset of columns — often
  sufficient and cheaper (smaller shuffle key)
- dropDuplicates() on specific columns reduces shuffle data volume significantly

AQE helps: spark.sql.adaptive.coalescePartitions.enabled=true (default) merges
small post-shuffle partitions. Tune spark.sql.shuffle.partitions for your data volume.""",
    ),

    KnowledgeEntry(
        rule_id="CY018",
        keywords=["orderby", "sort", "global", "shuffle", "limit", "topn", "sortwithinpartitions"],
        title="orderBy() without limit() — O(N log N) global sort with full shuffle",
        source_url="https://spark.apache.org/docs/latest/rdd-programming-guide.html",
        config_params=["spark.sql.shuffle.partitions"],
        content="""Spark RDD guide documents three sort patterns with different costs:
1. mapPartitions + .sorted: local sort per partition — no shuffle, cheapest
2. repartitionAndSortWithinPartitions: "sorts within partitions DURING the shuffle —
   more efficient than repartition() followed by sorting (pushes sorting into shuffle machinery)"
3. sortBy / orderBy: produces globally ordered result — requires full shuffle + O(N log N) sort

Global sort is one of the most expensive Spark operations. Shuffle intermediate files
"preserved until GC'd — can consume large disk space in long-running jobs."

Fixes:
- Top-N: df.orderBy(F.col("value").desc()).limit(N)
  Spark optimizes orderBy().limit(N) into TakeOrderedAndProject — uses a heap of size N,
  avoids full sort, reads each partition once
- Partition-local: df.sortWithinPartitions("timestamp") — no shuffle, O(P * (N/P) log(N/P))
- Within shuffle: repartitionAndSortWithinPartitions("key")""",
    ),

    KnowledgeEntry(
        rule_id="CY020",
        keywords=["udf", "python", "jvm", "serialization", "row", "catalyst", "tungsten", "arrow", "pandas"],
        title="Python UDF — disables Catalyst, Tungsten, and row-by-row JVM serialization",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=[],
        content="""Python UDFs simultaneously disable three Spark optimization layers:

1. CATALYST: UDF is opaque — Catalyst cannot optimize inside it, push predicates
   through it, or fold constants. Entire UDF expression excluded from CBO.

2. TUNGSTEN: Off-heap binary format bypassed. Data deserialized from Tungsten
   binary format to Python objects row-by-row via Py4J IPC.

3. SERIALIZATION: Spark tuning guide recommends Kryo for "10x faster, more compact"
   JVM serialization — but Kryo cannot help Python UDFs. The bottleneck is the
   JVM-to-Python process IPC (one Python subprocess per executor).

SQL performance tuning guide alternatives (fastest to slowest):
1. pyspark.sql.functions built-ins: F.upper(), F.regexp_replace(), F.when(), etc.
   — zero serialization, fully Catalyst-optimized
2. SQL expressions: df.withColumn("x", F.expr("case when a > 0 then a else 0 end"))
   — Catalyst-optimized
3. pandas_udf (Apache Arrow vectorized): ~2x overhead vs native (vs 10-100x for UDF)
   @pandas_udf(returnType=StringType())
   def my_fn(s: pd.Series) -> pd.Series: return s.str.upper()
4. Python UDF: only if no other option exists""",
    ),

    KnowledgeEntry(
        rule_id="CY050",
        keywords=["cartesian", "cross", "join", "product", "plan", "exchange", "nested", "critical"],
        title="CartesianProduct in execution plan — O(N*M) data explosion",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=["spark.sql.autoBroadcastJoinThreshold", "spark.sql.broadcastTimeout"],
        content="""SQL performance tuning guide: CartesianProduct is the physical implementation
of SHUFFLE_REPLICATE_NL join strategy — the lowest-priority strategy used only when
no equi-join key exists.

Consequences: N * M output rows where N, M = row counts of each side.
At 1M x 1M rows: 10^12 row pairs. At 100 bytes/row = 100 TB intermediate data.
AQE skew join optimization does NOT protect against CartesianProduct.

CartesianProduct in the execution plan is almost always a bug (missing join condition).
Legitimate use: crossJoin() on a very small table (< 10K rows) with an immediate filter.

Fixes:
- Add explicit equi-join condition: df.join(other, "id", how="inner")
- For small lookup tables: df.join(broadcast(small_df), "id")
  BroadcastNestedLoopJoin (threshold: spark.sql.autoBroadcastJoinThreshold=10MB)
  is far cheaper than CartesianProduct + full shuffle""",
    ),

    KnowledgeEntry(
        rule_id="CY051",
        keywords=["shuffle", "exchange", "sort", "aggregate", "network", "disk", "io", "wide"],
        title="Excessive Exchange nodes — cumulative shuffle cost",
        source_url="https://spark.apache.org/docs/latest/tuning.html",
        config_params=[
            "spark.sql.adaptive.enabled",
            "spark.sql.adaptive.coalescePartitions.enabled",
            "spark.sql.adaptive.advisoryPartitionSizeInBytes",
            "spark.sql.shuffle.partitions",
            "spark.local.dir",
            "spark.sql.sources.v2.bucketing.enabled",
        ],
        content="""Spark tuning guide defines shuffle cost precisely:
"Shuffle involves disk I/O, data serialization, and network I/O. Spark generates
map output files sorted and written to a single file per partition. Reduce tasks
read relevant sorted blocks. Intermediate files preserved until RDD GC'd."
Temporary files stored at spark.local.dir.

Each Exchange node in the physical plan = one full shuffle round. Wide transformations
that trigger shuffles: groupBy, join (non-broadcast), distinct, repartition, sortBy.

Official reduction strategies (SQL performance tuning guide):
1. AQE (default since Spark 3.2):
   - Coalesces small post-shuffle partitions (target: 64MB advisory size)
   - Converts SortMergeJoin to BroadcastHashJoin at runtime if one side is small
   - Splits skewed partitions dynamically
   Config: spark.sql.adaptive.advisoryPartitionSizeInBytes=64MB
2. Bucketing: pre-partition tables on join/groupBy keys — eliminates Exchange node
3. Storage Partition Join: spark.sql.sources.v2.bucketing.enabled=true (V2 sources)
4. Cache intermediate results before multiple downstream operations""",
    ),

    KnowledgeEntry(
        rule_id="CY052",
        keywords=["sortmergejoin", "broadcast", "join", "small", "threshold", "aqe", "runtime", "smj"],
        title="SortMergeJoin — broadcast conversion opportunity",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=[
            "spark.sql.autoBroadcastJoinThreshold",
            "spark.sql.adaptive.autoBroadcastJoinThreshold",
            "spark.sql.adaptive.enabled",
            "spark.sql.broadcastTimeout",
        ],
        content="""SQL performance tuning guide, AQE Feature 3 — Runtime SMJ to BHJ conversion:
"Benefits: avoids sorting both join sides; can read shuffle files locally
(avoids network traffic via local shuffle reader)."

Static threshold: spark.sql.autoBroadcastJoinThreshold=10MB (default).
Tables over 10MB use SortMergeJoin (full sort of both sides + shuffle).

AQE dynamic threshold: spark.sql.adaptive.autoBroadcastJoinThreshold
(defaults to spark.sql.autoBroadcastJoinThreshold).
AQE converts SMJ to BHJ at RUNTIME if actual shuffled bytes are below threshold.

Manual broadcast (preferred when small side is known at design time):
  from pyspark.sql.functions import broadcast
  df.join(broadcast(small_df), "id", how="inner")
  # SQL: SELECT /*+ BROADCAST(small_table) */ * FROM big JOIN small_table ON ...
  # Also accepts: BROADCASTJOIN, MAPJOIN hints

If physical plan shows SortMergeJoin with no broadcast:
- Run ANALYZE TABLE to update catalog statistics (tuning guide)
- Increase threshold: spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "50mb")
- Timeout: spark.sql.broadcastTimeout=300s — increase for slow networks""",
    ),

    KnowledgeEntry(
        rule_id="CY053",
        keywords=["window", "partition", "rank", "rownum", "over", "single", "executor", "spec"],
        title="Window function without partitionBy — single-executor global processing",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=["spark.sql.shuffle.partitions"],
        content="""Spark window functions use WindowSpec: Window.partitionBy(...).orderBy(...).
Without partitionBy(), the entire dataset is treated as ONE partition — functionally
equivalent to a global orderBy() (O(N log N) sort, full shuffle, single executor).

The SQL performance tuning guide classifies global sort as requiring:
"full shuffle + O(N log N) sort across all partitions" — one of the most expensive ops.

Physical plan: a single Window node processes all rows on ONE executor, creating
a memory and compute bottleneck regardless of cluster size.

Fix:
  w = Window.partitionBy("dept").orderBy(F.col("salary").desc())
  df.withColumn("rank", F.rank().over(w))
This distributes window computation: one executor handles each "dept" partition.
Number of distinct partitionBy values should match or exceed spark.sql.shuffle.partitions
for efficient parallelism.""",
    ),

    KnowledgeEntry(
        rule_id="CY054",
        keywords=["aqe", "adaptive", "disabled", "static", "plan", "optimization", "runtime", "exchange"],
        title="AQE not active — missing runtime re-optimization (5 features unavailable)",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=[
            "spark.sql.adaptive.enabled",
            "spark.sql.adaptive.coalescePartitions.enabled",
            "spark.sql.adaptive.skewJoin.enabled",
            "spark.sql.adaptive.autoBroadcastJoinThreshold",
            "spark.sql.adaptive.advisoryPartitionSizeInBytes",
        ],
        content="""SQL performance tuning guide: "AQE re-optimizes query plan mid-execution
based on accurate runtime statistics. Enabled by default since Spark 3.2.0."

Without AQE (spark.sql.adaptive.enabled=false), ALL 5 runtime features are unavailable:
1. Post-shuffle partition coalescing (merges tiny post-shuffle partitions)
2. Skewed partition splitting (splits large partitions in RebalancePartitions)
3. SMJ-to-BHJ conversion (converts SortMergeJoin to BroadcastHashJoin at runtime)
4. SMJ-to-ShuffledHashJoin conversion (when local hash map fits in memory)
5. Skew join optimization (splits + replicates skewed sort-merge join tasks)

Detection: physical plan with Exchange nodes but NO AdaptiveSparkPlan wrapper node
indicates AQE is disabled (or the query is too simple to trigger it).

Enable: spark.conf.set("spark.sql.adaptive.enabled", "true")
For busy clusters: spark.sql.adaptive.coalescePartitions.parallelismFirst=false
  (respects 64MB advisory size instead of maximizing parallelism)
Advisory target: spark.sql.adaptive.advisoryPartitionSizeInBytes=64MB""",
    ),

    KnowledgeEntry(
        rule_id="SHUFFLE_PARTITIONS",
        keywords=["shuffle", "partitions", "200", "default", "config", "tune", "performance", "sql"],
        title="spark.sql.shuffle.partitions=200 — fixed default ignores data volume",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=[
            "spark.sql.shuffle.partitions",
            "spark.sql.adaptive.enabled",
            "spark.sql.adaptive.coalescePartitions.enabled",
            "spark.sql.adaptive.advisoryPartitionSizeInBytes",
        ],
        content="""SQL performance tuning guide: spark.sql.shuffle.partitions=200 (default).
Spark tuning guide target: "2-3 tasks per CPU core" for reduce operations.

200 partitions is wrong for most workloads:
- 1TB dataset / 200 = 5GB per partition (too few — high memory pressure per task)
- 1GB dataset / 200 = 5MB per partition (too many — high scheduling overhead)

AQE (spark.sql.adaptive.coalescePartitions.enabled=true, default) automatically
merges small post-shuffle partitions — partially mitigates the fixed-200 problem.
AQE advisory target: spark.sql.adaptive.advisoryPartitionSizeInBytes=64MB.
Minimum: spark.sql.adaptive.coalescePartitions.minPartitionSize=1MB.

Manual tuning without AQE:
  partitions = executor_cores * num_executors * 3
  spark.conf.set("spark.sql.shuffle.partitions", str(partitions))""",
    ),

    KnowledgeEntry(
        rule_id="SKEW",
        keywords=["skew", "skewed", "partition", "imbalance", "salt", "hot", "key", "straggler"],
        title="Data skew — uneven partition sizes cause straggler executor tasks",
        source_url="https://spark.apache.org/docs/latest/sql-performance-tuning.html",
        config_params=[
            "spark.sql.adaptive.skewJoin.enabled",
            "spark.sql.adaptive.skewJoin.skewedPartitionFactor",
            "spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes",
            "spark.sql.adaptive.forceOptimizeSkewedJoin",
        ],
        content="""SQL performance tuning guide, AQE skew join optimization:
"Dynamically splits and replicates skewed sort-merge join tasks into evenly sized tasks."

Skew detection thresholds (official defaults):
  Skewed partition: size > (5.0 x median partition size) AND size > 256MB
  Config: spark.sql.adaptive.skewJoin.skewedPartitionFactor=5.0
          spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=256MB

Manual salting (when AQE cannot help):
  df.withColumn("salt", (F.rand() * N).cast("int"))  # distribute hot key
  .groupBy("key", "salt").agg(F.sum("value"))        # partial aggregate
  .groupBy("key").agg(F.sum("value"))                # final aggregate

Broadcast join (best remedy for small-table skew):
  Broadcast the skewed side if it fits in memory — threshold: autoBroadcastJoinThreshold=10MB.
  AQE auto-converts at runtime if runtime stats show one side is small.

Force skew optimization: spark.sql.adaptive.forceOptimizeSkewedJoin=true
  (forces optimization even if it introduces an extra shuffle)""",
    ),

    KnowledgeEntry(
        rule_id="BROADCAST_VAR",
        keywords=["broadcast", "variable", "lookup", "static", "reference", "driver", "task", "large"],
        title="Broadcast variables — distribute large read-only objects efficiently",
        source_url="https://spark.apache.org/docs/latest/tuning.html",
        config_params=["spark.sql.autoBroadcastJoinThreshold", "spark.sql.broadcastTimeout"],
        content="""Spark tuning guide: "If tasks use any large object from the driver (e.g., a
lookup table), convert it to a broadcast variable — greatly reduces serialized task size
and job launch cost. Tasks larger than ~20 KiB are probably worth broadcasting."

Broadcast variables use "efficient broadcast algorithms to reduce communication cost"
versus shipping one copy per task (which scales with task count, not executor count).
Spark automatically broadcasts common data within a single stage — explicit broadcast
variables are useful for cross-stage reuse only.

Best practices (from official docs):
  bcast = sc.broadcast(lookup_dict)      # create once on driver
  bcast.value                            # use on executors
  bcast.unpersist()                      # release — allows re-broadcast if reused
  bcast.destroy()                        # permanent removal — cannot use after

For DataFrames: from pyspark.sql.functions import broadcast
  df.join(broadcast(small_df), "key")   # hint Catalyst to use BroadcastHashJoin""",
    ),
]


class SparkKnowledgeBase:
    """
    Keyword-based retrieval from official Apache Spark documentation.

    Sources: spark.apache.org/docs/latest — Spark 4.1.1
      - tuning.html
      - sql-performance-tuning.html
      - rdd-programming-guide.html
    """

    def __init__(self) -> None:
        self._entries = _KNOWLEDGE_BASE
        self._by_rule: dict[str, KnowledgeEntry] = {e.rule_id: e for e in self._entries}

    def query(self, question: str, rule_id: str | None = None) -> str:
        if rule_id and rule_id in self._by_rule:
            return self._by_rule[rule_id].content

        q_lower = question.lower()
        tokens = set(re.findall(r"\w+", q_lower))

        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in self._entries:
            score = sum(1 for kw in entry.keywords if kw in tokens)
            if score > 0:
                scored.append((score, entry))

        if not scored:
            return ""
        scored.sort(key=lambda x: -x[0])
        return scored[0][1].content

    def query_with_config(self, rule_id: str) -> tuple[str, list[str]]:
        entry = self._by_rule.get(rule_id)
        if entry:
            return entry.content, entry.config_params
        return "", []

    def all_rules_context(self) -> str:
        return "\n\n".join(
            f"[{e.rule_id}] {e.title}\n{e.content}" for e in self._entries
        )

    def sources(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for e in self._entries:
            if e.source_url not in seen:
                seen.add(e.source_url)
                result.append(e.source_url)
        return result

    def get_config_params(self, rule_id: str) -> list[str]:
        entry = self._by_rule.get(rule_id)
        return entry.config_params if entry else []
