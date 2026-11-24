"""Create the metric alarms used in the Lab 6 live evidence window."""

from __future__ import annotations

import argparse

import boto3

ENDPOINT = "northstar-churn-prod"
NAMESPACE = "NorthStar/ChurnModel"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default="MaeAdmin")
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    cw = session.client("cloudwatch")

    cw.put_metric_alarm(
        AlarmName="northstar-inference-latency",
        AlarmDescription="Champion p95 ModelLatency above 200 ms for 3 of 5 one-minute periods (microseconds).",
        Namespace="AWS/SageMaker",
        MetricName="ModelLatency",
        Dimensions=[{"Name": "EndpointName", "Value": ENDPOINT},
                    {"Name": "VariantName", "Value": "champion"}],
        ExtendedStatistic="p95",
        Period=60,
        EvaluationPeriods=5,
        DatapointsToAlarm=3,
        Threshold=200000,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    cw.put_metric_alarm(
        AlarmName="northstar-model-drift",
        AlarmDescription="Evidently reports at least one feature outside its configured drift threshold.",
        Namespace=NAMESPACE,
        MetricName="DriftDetected",
        Dimensions=[{"Name": "EndpointName", "Value": ENDPOINT}],
        Statistic="Maximum",
        Period=300,
        EvaluationPeriods=1,
        Threshold=0.5,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    cw.put_metric_alarm(
        AlarmName="northstar-endpoint-availability",
        AlarmDescription="Endpoint 5xx rate exceeds 5% over five minutes.",
        Metrics=[
            {"Id": "invocations", "MetricStat": {
                "Metric": {"Namespace": "AWS/SageMaker", "MetricName": "Invocations",
                           "Dimensions": [{"Name": "EndpointName", "Value": ENDPOINT}]},
                "Period": 300, "Stat": "Sum"}, "ReturnData": False},
            {"Id": "errors", "MetricStat": {
                "Metric": {"Namespace": "AWS/SageMaker", "MetricName": "Invocation5XXErrors",
                           "Dimensions": [{"Name": "EndpointName", "Value": ENDPOINT}]},
                "Period": 300, "Stat": "Sum"}, "ReturnData": False},
            {"Id": "error_rate", "Expression": "IF(invocations>0,errors/invocations,0)",
             "Label": "5xx error rate", "ReturnData": True},
        ],
        EvaluationPeriods=1,
        Threshold=0.05,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    print("created northstar endpoint availability, inference latency, and model drift alarms")


if __name__ == "__main__":
    main()
