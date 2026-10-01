"""
Glue ETL: processed/customers/ -> features/customers/ + SageMaker Feature Store

TEMPORAL SPLIT - read this before changing anything
---------------------------------------------------
    |<---- observation window ---->|<--- holdout --->|
                              FEATURE_CUTOFF (T)   SNAPSHOT

  * Every feature is computed ONLY from purchases on or before T.
  * churn_label is derived ONLY from the holdout: 1 if the customer made
    no purchase in (T, SNAPSHOT], else 0.

Mixing the two windows is the classic leakage failure. If recency were
computed over the full range, it would encode the answer directly and the
model would post a near-perfect AUC that collapses in production.

Note that roughly a third of churners are still buying right up to T. A
model using recency alone misses them; that is precisely why the rest of
the feature set exists.

This is also where the grain changes. Input is transaction level (many rows
per customer); output is customer level (exactly one row per customer). Every
feature is an aggregate over that customer's purchase history.

Job arguments (wired by Terraform in modules/glue):
  --input_path         s3:// processed Parquet
  --output_path        s3:// features destination
  --feature_group_name SageMaker Feature Group to ingest into
  --region             AWS region for the Feature Store runtime client
"""

import sys
import time

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

# Loyalty tier thresholds on total lifetime value (USD).
TIER_BRONZE_MAX = 500.0
TIER_SILVER_MAX = 2000.0
TIER_GOLD_MAX = 5000.0

# Churn risk bands. The score is a rule-based proxy, not a model - Lab 3
# replaces it with a trained prediction. It exists so the feature vector has
# a plausible label-shaped column to work with in the meantime.
RISK_HIGH_LO, RISK_HIGH_HI = 0.7, 1.0
RISK_MED_LO, RISK_MED_HI = 0.4, 0.7
RISK_LOW_LO, RISK_LOW_HI = 0.0, 0.4

# Timeline anchors. These MUST match the generator that produced the raw data.
FEATURE_CUTOFF = "2026-04-01"   # T - features use data on or before this date
SNAPSHOT = "2026-06-30"         # end of the holdout window

N_CATEGORIES = 8.0              # denominator for category_diversity_score


def split_windows(df):
    """Split into the observation window and outcome window."""
    cutoff = F.to_date(F.lit(FEATURE_CUTOFF))
    snapshot = F.to_date(F.lit(SNAPSHOT))

    history = df.filter(F.col("purchase_date") <= cutoff)

    holdout = df.filter(
        (F.col("purchase_date") > cutoff)
        & (F.col("purchase_date") <= snapshot)
    )

    return history, holdout


def compute_rfm_features(history):
    """Aggregate transaction history into one row per customer."""
    cutoff = F.to_date(F.lit(FEATURE_CUTOFF))

    in_30d = F.col("purchase_date") >= F.date_sub(cutoff, 30)
    in_90d = F.col("purchase_date") >= F.date_sub(cutoff, 90)
    in_180d = F.col("purchase_date") >= F.date_sub(cutoff, 180)

    orders_180d = F.sum(
        F.when(in_180d, F.lit(1)).otherwise(F.lit(0))
    )

    items_180d = F.sum(
        F.when(in_180d, F.col("num_items")).otherwise(F.lit(0))
    )

    online_orders = F.sum(
        F.when(F.col("channel") == "online", F.lit(1))
         .otherwise(F.lit(0))
    )

    total_orders = F.count(F.lit(1))

    return history.groupBy("customer_id").agg(
        F.datediff(cutoff, F.max("purchase_date"))
         .cast("double")
         .alias("days_since_last_purchase"),

        F.datediff(cutoff, F.min("purchase_date"))
         .cast("double")
         .alias("customer_tenure_days"),

        F.sum(F.when(in_30d, 1).otherwise(0))
         .cast("double")
         .alias("purchase_frequency_30d"),

        F.sum(F.when(in_90d, 1).otherwise(0))
         .cast("double")
         .alias("purchase_frequency_90d"),

        F.sum(F.when(in_180d, 1).otherwise(0))
         .cast("double")
         .alias("purchase_frequency_180d"),

        F.avg("order_value")
         .cast("double")
         .alias("avg_order_value"),

        F.sum(
            F.when(in_90d, F.col("order_value"))
             .otherwise(F.lit(0.0))
        )
        .cast("double")
        .alias("total_spend_90d"),

        F.sum("order_value")
         .cast("double")
         .alias("total_lifetime_value"),

        F.when(
            orders_180d > 0,
            items_180d / orders_180d
        )
        .otherwise(F.lit(0.0))
        .cast("double")
        .alias("avg_basket_size_6m"),

        (
            F.countDistinct(
                F.when(
                    F.col("product_category") != "unknown",
                    F.col("product_category")
                )
            ).cast("double") / F.lit(N_CATEGORIES)
        )
        .alias("category_diversity_score"),

        (online_orders / total_orders)
        .cast("double")
        .alias("online_to_store_ratio"),
    )

def assign_loyalty_tier(df):
    """Assign loyalty tier from total lifetime value."""
    return df.withColumn(
        "loyalty_tier",
        F.when(
            F.col("total_lifetime_value") < TIER_BRONZE_MAX,
            F.lit("Bronze"),
        )
        .when(
            F.col("total_lifetime_value") < TIER_SILVER_MAX,
            F.lit("Silver"),
        )
        .when(
            F.col("total_lifetime_value") < TIER_GOLD_MAX,
            F.lit("Gold"),
        )
        .otherwise(F.lit("Platinum")),
    )

def compute_churn_proxy(df):
    """Compute a scaled rule-based churn risk score."""
    days = F.col("days_since_last_purchase")
    frequency_30d = F.col("purchase_frequency_30d")

    high_risk = (days > 60) & (frequency_30d == 0)
    medium_risk = days > 30

    high_score = F.lit(RISK_HIGH_LO) + F.lit(0.3) * F.least(
        F.lit(1.0),
        F.greatest(F.lit(0.0), (days - F.lit(60.0)) / F.lit(90.0)),
    )

    medium_score = F.lit(RISK_MED_LO) + F.lit(0.3) * F.least(
        F.lit(1.0),
        F.greatest(F.lit(0.0), (days - F.lit(30.0)) / F.lit(30.0)),
    )

    low_score = F.lit(RISK_LOW_LO) + F.lit(0.4) * F.least(
        F.lit(1.0),
        F.greatest(F.lit(0.0), days / F.lit(30.0)),
    )

    return df.withColumn(
        "churn_risk_score",
        F.when(high_risk, high_score)
         .when(medium_risk, medium_score)
         .otherwise(low_score)
         .cast("double"),
    )

def attach_churn_label(features, holdout):
    """Label customers who made no purchase in the outcome window."""
    outcome_customers = (
        holdout.select("customer_id")
        .distinct()
        .withColumn("_purchased_in_outcome", F.lit(1))
    )

    return (
        features.join(outcome_customers, on="customer_id", how="left")
        .withColumn(
            "churn_label",
            F.when(
                F.col("_purchased_in_outcome").isNull(),
                F.lit(1),
            )
            .otherwise(F.lit(0))
            .cast("int"),
        )
        .drop("_purchased_in_outcome")
    )

def ingest_to_feature_store(rows, feature_group_name, region, event_time):
    """PutRecord each customer into the online store.

    Runs on the driver against a collected list. That is acceptable here
    because the output is one row per customer (~10k records) - at production
    scale this would be a foreachPartition with a client per partition.
    """
    client = boto3.client("sagemaker-featurestore-runtime", region_name=region)
    ingested = 0
    for r in rows:
        record = [
            {"FeatureName": "customer_id", "ValueAsString": str(r["customer_id"])},
            # event_time is Fractional: send epoch seconds as a numeric string.
            # An ISO 8601 timestamp here is accepted and then silently dropped.
            {"FeatureName": "event_time", "ValueAsString": str(event_time)},
        ] + [
            {"FeatureName": name, "ValueAsString": str(r[name])}
            for name in [
                "days_since_last_purchase", "customer_tenure_days",
                "purchase_frequency_30d", "purchase_frequency_90d",
                "purchase_frequency_180d", "avg_order_value", "total_spend_90d",
                "total_lifetime_value", "avg_basket_size_6m",
                "category_diversity_score", "online_to_store_ratio",
                "loyalty_tier", "churn_risk_score", "churn_label",
            ]
        ]
        client.put_record(FeatureGroupName=feature_group_name, Record=record)
        ingested += 1
    return ingested


def main():
    args = getResolvedOptions(
        sys.argv,
        ["JOB_NAME", "input_path", "output_path", "feature_group_name", "region"],
    )

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    df = spark.read.parquet(args["input_path"])
    print(f"[features] read {df.count()} processed transaction rows")

    history, holdout = split_windows(df)
    print(f"[features] observation window (<= {FEATURE_CUTOFF}): {history.count()} rows")
    print(f"[features] holdout window ({FEATURE_CUTOFF} to {SNAPSHOT}): {holdout.count()} rows")

    features = compute_rfm_features(history)
    features = assign_loyalty_tier(features)
    features = compute_churn_proxy(features)
    features = attach_churn_label(features, holdout)

    for col in ["avg_order_value", "total_lifetime_value", "total_spend_90d",
                "avg_basket_size_6m", "category_diversity_score", "online_to_store_ratio"]:
        features = features.withColumn(col, F.round(F.col(col), 4))

    n_customers = features.count()
    print(f"[features] computed features for {n_customers} customers")

    # Producer-side quality gates. Failing here beats shipping a broken
    # feature set that Lab 3 trains on.
    for col in ["days_since_last_purchase", "customer_tenure_days",
                "purchase_frequency_30d", "purchase_frequency_90d",
                "purchase_frequency_180d", "avg_order_value", "total_spend_90d",
                "total_lifetime_value", "avg_basket_size_6m",
                "category_diversity_score", "online_to_store_ratio",
                "loyalty_tier", "churn_risk_score", "churn_label"]:
        nulls = features.filter(F.col(col).isNull()).count()
        assert nulls == 0, f"{col} has {nulls} null values"

    out_of_range = features.filter(
        (F.col("churn_risk_score") < 0) | (F.col("churn_risk_score") > 1)
    ).count()
    assert out_of_range == 0, f"churn_risk_score out of [0,1] for {out_of_range} rows"

    churn_rate = features.agg(F.avg("churn_label")).collect()[0][0]
    print(f"[features] churn_label rate: {churn_rate:.1%}")
    assert 0.05 < churn_rate < 0.50, \
        f"churn rate {churn_rate:.1%} is implausible - check the window split"

    tiers = {r["loyalty_tier"] for r in features.select("loyalty_tier").distinct().collect()}
    print(f"[features] tier distribution present: {sorted(tiers)}")
    assert tiers == {"Bronze", "Silver", "Gold", "Platinum"}, \
        f"tier distribution is degenerate: {sorted(tiers)}"

    event_time = float(int(time.time()))
    features = features.withColumn("event_time", F.lit(event_time))

    (features.coalesce(2)
             .write
             .mode("overwrite")
             .parquet(args["output_path"]))
    print(f"[features] wrote {n_customers} rows to {args['output_path']}")

    rows = [r.asDict() for r in features.collect()]
    ingested = ingest_to_feature_store(
        rows, args["feature_group_name"], args["region"], event_time
    )
    print(f"[features] ingested {ingested} records into "
          f"{args['feature_group_name']} at event_time {event_time}")

    job.commit()


if __name__ == "__main__":
    main()
