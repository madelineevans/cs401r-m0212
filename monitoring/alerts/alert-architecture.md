# NorthStar alert architecture

All alert names include `northstar` so the Lab 6 teardown script can find and
remove the alarms. The on-call uses the role-based escalation below; page or
ticket routing should be connected to the course team's actual notification
endpoint before production use.

| Alert | Signal and threshold | Tier | Escalation | Recovery / notes |
|---|---|---:|---|---|
| `northstar-endpoint-availability` | SageMaker `Invocation5XXErrors` > 5% of invocations over 5 minutes, 2 periods | P1 | Wake on-call and page service manager | Check endpoint health, capacity, and latest deployment; roll back if release-related |
| `northstar-inference-latency` | Champion `ModelLatency` p95 > 200000 µs for 3 of 5 one-minute periods | P2 | Page ML engineer on-call | Inspect CPU, memory, and request load; use Lab 5 rollback if canary causes the spike |
| `northstar-model-drift` | `DriftDetected` = 1 after an adequately powered (≥500-row) Evidently run | P2 | Page ML engineer on-call and notify model owner | Check report and affected features; suppress only during planned retraining window |
| `northstar-glue-job-failure` | EventBridge Glue Job State Change with state `FAILED`, `ERROR`, or `TIMEOUT` | P3 | Post in operations Slack channel and open a ticket | Inspect Glue run error and S3 permissions; retry after correction |
| `northstar-churn-alert-volume-drop` | `ChurnAlertVolume` is >30% below the trailing 7-day same-day average for 2 daily evaluations | P3 | Post in operations Slack channel and open a ticket | Check capture coverage and score distribution before changing campaign volume |
| `northstar-fairness-recall-gap` | Weekly recall@10 gap across loyalty tiers > 0.10 absolute | P2 | Page model owner and fairness reviewer | Pause promotion; validate sample sizes and tier-level recall |
| `northstar-capture-missing` | No new capture objects for 15 minutes while endpoint receives requests | P4 | Ticket only | Check DataCaptureConfig and MLEngineer S3 capture permissions |
| `northstar-monitoring-window-underpowered` | Fewer than 500 distinct predictions in the comparison window | P4 | Ticket only | Collect additional traffic; do not interpret drift from this run |

## Tier routing

- **P1:** wake the on-call immediately and page the service manager; acknowledge
  within 5 minutes and provide a mitigation update within 15 minutes.
- **P2:** page the ML engineer on-call; acknowledge within 15 minutes and name
  an incident lead if unresolved after 30 minutes.
- **P3:** send a Slack notification and create a tracked ticket for the next
  staffed shift; the on-call triages within 4 business hours.
- **P4:** create a ticket only; the monitoring owner reviews it within one
  business day.

## Suppression rule

During the approved weekly retraining window (Tuesday 02:00–04:00 UTC), suppress
only `northstar-model-drift` (P2) and `northstar-churn-alert-volume-drop` (P3)
while the retraining job is active. Keep the suppression bounded to that
window and require the retraining job to emit a completion/failure event. Never
suppress availability, latency, Glue failure, fairness, capture-loss, or
underpowered-window alerts. Re-evaluate drift after the new model's baseline is
approved; a failed or overlong training run expires the suppression.

`ModelLatency` values in AWS and all IaC thresholds are microseconds: 200 ms is
`200000`, and 500 ms is `500000`.
