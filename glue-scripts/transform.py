"""
Glue ETL: raw/customers/ -> processed/customers/

Reads the crawler-registered catalog table, enforces types, imputes nulls,
removes duplicate transactions, and writes Parquet to the processed zone.

Grain note: this job is transaction-level in and transaction-level out. One
row per purchase, many rows per customer. The feature engineering job is
what collapses to one row per customer. Deduplicating on customer_id here
would destroy the purchase history that RFM features are computed from.

Job arguments (wired by Terraform in modules/glue):
  --database_name  Glue catalog database
  --table_name     catalog table produced by the crawler
  --output_path    s3:// destination for Parquet output
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Target types for the processed zone. The crawler infers everything from CSV
# as string, so every one of these is an explicit cast, not a no-op.
SCHEMA = {
    "transaction_id": "string",
    "customer_id": "string",
    "purchase_date": "date",
    "order_value": "double",
    "num_items": "int",
    "payment_method": "string",
    "channel": "string",
    "store_id": "string",
    "product_category": "string",
}

NUMERIC_COLS = ["order_value", "num_items"]
STRING_COLS = ["payment_method", "channel", "store_id", "product_category"]


def cast_types(df):
    """Cast every column to its SCHEMA type. Drop rows with no customer_id."""
    # Trim whitespace from every crawler-inferred string column.
    for column in df.columns:
        df = df.withColumn(column, F.trim(F.col(column)))

    # Convert empty strings to null.
    for column in df.columns:
        df = df.withColumn(
            column,
            F.when(F.length(F.col(column)) == 0, F.lit(None))
             .otherwise(F.col(column))
        )

    # Parse both supported date formats.
    df = df.withColumn(
        "purchase_date",
        F.coalesce(
            F.to_date(F.col("purchase_date"), "yyyy-MM-dd"),
            F.to_date(F.col("purchase_date"), "MM/dd/yyyy"),
        ),
    )

    # Enforce the target schema.
    for column, data_type in SCHEMA.items():
        df = df.withColumn(column, F.col(column).cast(data_type))

    return df.filter(F.col("customer_id").isNotNull())

def impute_nulls(df):
    """Numeric columns -> column median. String columns -> 'unknown'."""
    for column in NUMERIC_COLS:
        median_values = df.approxQuantile(column, [0.5], 0.0)

        if not median_values:
            raise ValueError(f"Cannot calculate median for {column}")

        median = median_values[0]

        if column == "num_items":
            median = int(round(median))

        df = df.na.fill({column: median})

    for column in STRING_COLS:
        df = df.na.fill({column: "unknown"})

    return df


def deduplicate(df):
    """Keep one row per transaction_id."""
    window = Window.partitionBy("transaction_id").orderBy(
        F.col("purchase_date").desc_nulls_last(),
        F.col("order_value").desc_nulls_last(),
        F.col("num_items").desc_nulls_last(),
    )

    return (
        df.withColumn("_row_number", F.row_number().over(window))
          .filter(F.col("_row_number") == 1)
          .drop("_row_number")
    )


def main():
    args = getResolvedOptions(
        sys.argv, ["JOB_NAME", "database_name", "table_name", "output_path"]
    )

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    dyf = glue_context.create_dynamic_frame.from_catalog(
        database=args["database_name"],
        table_name=args["table_name"],
    )
    df = dyf.toDF()
    raw_count = df.count()
    print(f"[transform] read {raw_count} raw rows from "
          f"{args['database_name']}.{args['table_name']}")

    df = cast_types(df)
    after_cast = df.count()
    print(f"[transform] after cast_types: {after_cast} rows "
          f"({raw_count - after_cast} dropped for null customer_id)")

    df = impute_nulls(df)
    print(f"[transform] after impute_nulls: {df.count()} rows")

    df = deduplicate(df)
    final_count = df.count()
    print(f"[transform] after deduplicate: {final_count} rows "
          f"({after_cast - final_count} duplicate transactions removed)")

    # Fail loudly rather than writing a bad dataset the feature job will
    # silently consume. These are the same guarantees the data contract
    # published for processed/customers/, enforced at the producer.
    assert df.filter(F.col("customer_id").isNull()).count() == 0, \
        "null customer_id survived the transform"
    assert df.select("transaction_id").distinct().count() == final_count, \
        "duplicate transaction_id survived the transform"
    assert df.filter(F.col("purchase_date").isNull()).count() == 0, \
        "unparseable purchase_date survived the transform"

    (df.coalesce(4)
       .write
       .mode("overwrite")
       .parquet(args["output_path"]))
    print(f"[transform] wrote {final_count} rows to {args['output_path']}")

    job.commit()


if __name__ == "__main__":
    main()
