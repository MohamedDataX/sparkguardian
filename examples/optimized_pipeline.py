"""Example of optimized PySpark code — SparkGuardian compliant."""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.appName("OptimizedPipeline").getOrCreate()

df = spark.read.parquet("s3://bucket/data/")

# Use take(n) instead of collect()
sample = df.take(100)

# Cache before multiple actions
df.cache()
n = df.count()

# coalesce(1) instead of repartition(1)
df_single = df.coalesce(1)

# Native Spark function instead of UDF
df = df.withColumn("name_upper", F.upper(F.col("name")))

# Batch withColumn → single select
df = df.select(
    "*",
    F.lit(1).alias("a"),
    F.lit(2).alias("b"),
    F.lit(3).alias("c"),
    F.lit(4).alias("d"),
    F.lit(5).alias("e"),
)

# Explicit join type
df2 = spark.read.parquet("s3://bucket/other/")
joined = df.join(df2, "id", how="inner")

# Explicit column selection
result = df.select("id", "name", "value")

# Broadcast small table
small_df = spark.read.parquet("s3://bucket/small/")
joined_broadcast = df.join(F.broadcast(small_df), "id", how="left")

result.write.parquet("s3://bucket/output/")
