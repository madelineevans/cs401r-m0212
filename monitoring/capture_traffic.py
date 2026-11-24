"""Send distinct, one-row requests for a trustworthy Lab 6 capture window."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import boto3
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="monitoring/baseline/baseline.csv")
    parser.add_argument("--endpoint", default="northstar-churn-prod")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default="MaeAdmin")
    args = parser.parse_args()
    if args.count < 500:
        raise SystemExit("Use at least 500 invocations so the capture window can meet the drift minimum")

    frame = pd.read_csv(Path(args.baseline))[FEATURE_COLUMNS].drop_duplicates()
    if len(frame) < args.count:
        raise SystemExit(f"Need {args.count} distinct baseline rows; found {len(frame)}")
    requests = frame.sample(n=args.count, random_state=6)

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    runtime = session.client("sagemaker-runtime")
    variants: Counter[str] = Counter()
    for index, (_, row) in enumerate(requests.iterrows(), start=1):
        payload = ",".join(format(float(value), ".10g") for value in row.tolist())
        response = runtime.invoke_endpoint(
            EndpointName=args.endpoint,
            ContentType="text/csv",
            Body=payload,
        )
        variants[response["InvokedProductionVariant"]] += 1
        if index % 100 == 0:
            print(f"sent {index}/{args.count}; split so far: {dict(variants)}", flush=True)

    print(json.dumps({"endpoint": args.endpoint, "invocations": args.count,
                      "distinct_inputs": len(requests), "variant_counts": dict(variants)}, indent=2))


if __name__ == "__main__":
    main()
