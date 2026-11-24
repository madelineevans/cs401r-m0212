"""Publish model drift and daily churn-alert proxy metrics from a laptop.

Processing containers must not publish these metrics: the pinned Evidently
install changes the container's botocore dependencies. Run after the job has
completed and its drift_violations.json has been downloaded locally.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone

import boto3

NAMESPACE = "NorthStar/ChurnModel"


def scalar_score(raw: str) -> float | None:
    try:
        row = next(csv.reader([raw.strip().strip('"')]))
        return float(row[0].strip().strip('"')) if len(row) == 1 else None
    except (ValueError, StopIteration):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, help="Local drift_violations.json from a completed job")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--endpoint", default="northstar-churn-prod")
    parser.add_argument("--variant", default="champion")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--alert-score-threshold", type=float, default=0.5)
    args = parser.parse_args()

    with open(args.summary, encoding="utf-8") as stream:
        summary = json.load(stream)
    if summary.get("underpowered_window") or int(summary.get("captured_records", 0)) < 500:
        raise SystemExit("Refusing to publish: drift comparison window has fewer than 500 distinct records")

    s3 = boto3.client("s3", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)
    prefix = f"datacapture/{args.endpoint}/{args.variant}/"
    today = datetime.now(timezone.utc).date()
    seen = set()
    alert_count = 0
    valid_today = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=args.bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            body = s3.get_object(Bucket=args.bucket, Key=obj["Key"])["Body"].read().decode("utf-8")
            for line in body.splitlines():
                try:
                    record = json.loads(line)
                    metadata = record.get("eventMetadata", {})
                    timestamp = metadata.get("inferenceTime")
                    if not timestamp or datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date() != today:
                        continue
                    inputs = record["captureData"]["endpointInput"]["data"].strip()
                    output = record["captureData"]["endpointOutput"]["data"].strip()
                except (json.JSONDecodeError, KeyError, ValueError, AttributeError):
                    continue
                identity = (inputs, output)
                if identity in seen:
                    continue
                seen.add(identity)
                score = scalar_score(output)
                if score is None:
                    continue
                valid_today += 1
                alert_count += score >= args.alert_score_threshold

    if valid_today == 0:
        raise SystemExit(f"No distinct, parseable prediction outputs for {today} under s3://{args.bucket}/{prefix}")

    dimensions = [{"Name": "EndpointName", "Value": args.endpoint}]
    now = datetime.now(timezone.utc)
    cw.put_metric_data(
        Namespace=NAMESPACE,
        MetricData=[
            {
                "MetricName": "DriftDetected",
                "Dimensions": dimensions,
                "Timestamp": now,
                "Value": 1 if summary.get("drift_detected") else 0,
                "Unit": "Count",
            },
            {
                "MetricName": "ChurnAlertVolume",
                "Dimensions": dimensions,
                "Timestamp": now,
                "Value": alert_count,
                "Unit": "Count",
            },
        ],
    )
    print(f"published DriftDetected={int(bool(summary.get('drift_detected')))}")
    print(f"published ChurnAlertVolume={alert_count} from {valid_today} distinct predictions for {today} UTC")


if __name__ == "__main__":
    main()
