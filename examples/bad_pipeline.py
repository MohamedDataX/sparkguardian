"""Example of PySpark code with common anti-patterns — for SparkGuardian demo."""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

spark = SparkSession.builder.appName("BadPipeline").getOrCreate()

df = spark.read.parquet("s3://bucket/data/")

# CY001: .collect() driver memory risk
rows = df.collect()

# CY003: .count() full scan
n = df.count()
print(f"Row count: {n}")

# CY008: repartition(1) → should use coalesce(1)
df_single = df.repartition(1)

# CY002: .toPandas() large materialization
pdf = df.toPandas()

# CY020: Python UDF instead of native functions
@F.udf(StringType())
def upper_name(name):
    return name.upper() if name else None

df = df.withColumn("name_upper", upper_name(F.col("name")))

# CY009: Chained withColumn (5+)
df = (
    df.withColumn("a", F.lit(1))
    .withColumn("b", F.lit(2))
    .withColumn("c", F.lit(3))
    .withColumn("d", F.lit(4))
    .withColumn("e", F.lit(5))
)

# CY010: join without how=
df2 = spark.read.parquet("s3://bucket/other/")
joined = df.join(df2, "id")

# CY011: select("*")
wide_df = df.select("*")

# CY004: Spark action inside loop
for i in range(10):
    subset = df.filter(F.col("value") > i)
    count = subset.count()  # cy:ignore CY003
    print(count)

# CY005: .show() in production
df.show()
