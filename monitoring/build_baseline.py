"""Export the Lab 2 customer training features in endpoint input order.

Usage:
  python monitoring/build_baseline.py path/to/training-features.csv monitoring/baseline/baseline.csv
  python monitoring/build_baseline.py path/to/parquet/parts/ monitoring/baseline/baseline.csv

The source must be the Lab 2 training customer feature set. This deliberately
does not invent rows or include customer IDs, churn labels, or churn proxies.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

FEATURE_COLUMNS = [
    "days_since_last_purchase",
    "customer_tenure_days",
    "purchase_frequency_30d",
    "purchase_frequency_90d",
    "purchase_frequency_180d",
    "avg_order_value",
    "total_spend_90d",
    "total_lifetime_value",
    "avg_basket_size_6m",
    "category_diversity_score",
    "online_to_store_ratio",
]


def read_input(path: Path) -> pd.DataFrame:
    if path.is_dir():
        files = sorted([*path.glob("*.csv"), *path.glob("*.parquet")])
    else:
        files = [path]
    if not files:
        raise SystemExit(f"No CSV or Parquet feature files found at {path}")

    frames = []
    for file in files:
        if file.suffix.lower() == ".csv":
            frames.append(pd.read_csv(file))
        elif file.suffix.lower() == ".parquet":
            frames.append(pd.read_parquet(file))
        else:
            raise SystemExit(f"Unsupported input file: {file}")
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("training_features", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()

    frame = read_input(args.training_features)
    missing = [name for name in FEATURE_COLUMNS if name not in frame.columns]
    if missing:
        raise SystemExit(f"Training feature data is missing endpoint inputs: {missing}")
    baseline = frame.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if baseline.isna().any().any():
        raise SystemExit("Feature data contains null or nonnumeric model inputs; fix source data before export")
    if len(baseline) < 500:
        raise SystemExit(f"Only {len(baseline)} baseline rows; expected at least 500 training customers")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(args.output_csv, index=False, float_format="%.10g")
    print(f"wrote {len(baseline)} customers x {len(FEATURE_COLUMNS)} endpoint features to {args.output_csv}")


if __name__ == "__main__":
    main()
