# NorthStar Lab 2 Data Contract

## Purpose

This contract defines the datasets produced by the Lab 2 customer churn
pipeline. The producer is the Glue ETL pipeline; the consumers are feature
engineering, SageMaker Feature Store, and the Lab 3 training workflow.

## Sources and destinations

| Zone | Location | Producer | Consumer |
|---|---|---|---|
| Raw | `s3://<data-bucket>/raw/customers/` | Lab 2 upload | Glue crawler |
| Processed | `s3://<data-bucket>/processed/customers/` | `northstar-dev-transform` | Feature engineering job |
| Features | `s3://<data-bucket>/features/customers/` | `northstar-dev-feature-engineer` | SageMaker Feature Store and Lab 3 |

The bucket name is environment-specific and is formed as
`<project>-<environment>-data-<account-id>` by Terraform.

## Schema

### Raw and processed transaction records

The processed dataset preserves transaction-level grain and contains these
non-null, typed columns:

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `transaction_id` | string | No | Stable transaction identifier; deduplication key |
| `customer_id` | string | No | Customer identifier used for feature aggregation |
| `purchase_date` | date | No | Purchase date parsed from the source CSV |
| `order_value` | double | No | Order value in USD |
| `num_items` | integer | No | Number of items in the order |
| `payment_method` | string | No | Payment method; missing values become `unknown` |
| `channel` | string | No | `store`, `online`, or `unknown` |
| `store_id` | string | No | Store identifier or `ONLINE` |
| `product_category` | string | No | Product category; missing values become `unknown` |

### Engineered customer features

The feature dataset has exactly one row per customer. Features are calculated
from purchases on or before `FEATURE_CUTOFF = 2026-04-01`:

| Column | Feature Store type | Description |
|---|---|---|
| `customer_id` | String | Record identifier |
| `event_time` | Fractional | Epoch event time supplied to Feature Store |
| `days_since_last_purchase` | Fractional | Days from cutoff to the latest historical purchase |
| `customer_tenure_days` | Fractional | Days from the earliest historical purchase to cutoff |
| `purchase_frequency_30d` | Fractional | Historical purchases in the preceding 30 days |
| `purchase_frequency_90d` | Fractional | Historical purchases in the preceding 90 days |
| `purchase_frequency_180d` | Fractional | Historical purchases in the preceding 180 days |
| `avg_order_value` | Fractional | Mean historical order value |
| `total_spend_90d` | Fractional | Historical spend in the preceding 90 days |
| `total_lifetime_value` | Fractional | Total historical spend |
| `avg_basket_size_6m` | Fractional | Mean item count per order in the preceding 180 days |
| `category_diversity_score` | Fractional | Distinct known categories divided by 8 |
| `online_to_store_ratio` | Fractional | Online orders divided by all historical orders |
| `loyalty_tier` | String | Bronze, Silver, Gold, or Platinum |
| `churn_risk_score` | Fractional | Rule-based risk proxy in the range 0 to 1 |
| `churn_label` | Integral | 1 if no purchase occurs in `(2026-04-01, 2026-06-30]`, else 0 |

## Grain

- Raw and processed datasets are transaction-level: one row per unique
  `transaction_id`, with many rows allowed for the same `customer_id`.
- The feature dataset is customer-level: exactly one row per `customer_id`.
- `transaction_id` must be unique in the processed zone.

## Quality Guarantee

The producer must enforce these guarantees before publishing output:

- No null `customer_id` or `purchase_date` in processed output.
- No duplicate `transaction_id` in processed output.
- Numeric nulls are imputed with the column median; string nulls are `unknown`.
- Every feature row has non-null feature values.
- `churn_risk_score` is within `[0, 1]`.
- `churn_label` is an integer and is derived only from the outcome window.
- Feature rows use only history through `2026-04-01`; the outcome window is not
  used to calculate features.
- The expected churn rate is approximately 15–30% for the supplied sample.

If a quality assertion fails, the Glue job must fail rather than publish a
partial or silently invalid dataset.

## SLA / Service Level

- The raw transaction batch is available before the scheduled Glue crawl.
- The transform and feature-engineering jobs complete within the configured
  60-minute Glue timeout.
- The weekly Lab 3 scoring workflow must have an up-to-date feature snapshot
  before the Monday 6:00 AM ET campaign deadline.
- Feature Store online records are available after the feature-engineering job
  completes successfully.

## Retention and security

- Raw data is retained according to the Terraform S3 lifecycle policy.
- S3 public access is blocked and server-side encryption is enabled.
- The DataEngineer role can write only the raw, processed, and features data
  prefixes plus read Glue scripts.
- No credentials, raw secrets, or customer email addresses are stored in this
  pipeline.

## Versioning and breaking changes

This contract is versioned with the repository and the Terraform deployment.
Adding a nullable field is backward compatible. Renaming a field, changing a
Feature Store type, changing dataset grain, changing the cutoff semantics, or
removing a required field is a breaking change and requires a new contract
version plus coordinated consumer updates.
