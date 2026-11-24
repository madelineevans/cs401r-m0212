"""Create the Lab 6 dashboard and save its body as returned by CloudWatch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3

DASHBOARD_NAME = "NorthStar-AI-Platform"
DASHBOARD_FILE = Path("monitoring/dashboards/northstar-dashboard.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    client = boto3.client("cloudwatch", region_name=args.region)

    body = json.loads(DASHBOARD_FILE.read_text(encoding="utf-8"))
    response = client.put_dashboard(
        DashboardName=DASHBOARD_NAME,
        DashboardBody=json.dumps(body, separators=(",", ":")),
    )
    if response.get("DashboardValidationMessages"):
        raise SystemExit(json.dumps(response["DashboardValidationMessages"], indent=2))

    exported = client.get_dashboard(DashboardName=DASHBOARD_NAME)
    DASHBOARD_FILE.write_text(
        json.dumps(json.loads(exported["DashboardBody"]), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"created and exported {DASHBOARD_NAME} to {DASHBOARD_FILE}")


if __name__ == "__main__":
    main()
