# Lab 6 — Monitoring and Reliability Runbook

## Drift detection plan

### Drift types for NorthStar

- **Data drift is the leading near-term risk.** Holiday campaigns change purchase
  recency and frequency; catalog refreshes change category diversity and basket
  value; promotions can temporarily change average order value and channel mix.
  These changes can make the live customer population differ from the Lab 2
  training customers even when the model code is unchanged.
- **Concept drift is likely over a longer horizon.** Economic shifts, competitor
  activity, and changes in NorthStar's offer strategy can change which customers
  churn for a given feature profile. The relationship between features and
  eventual churn can move while the input distributions remain stable.
- **Model degradation is the outcome to detect, not a separate input shift.**
  AUC/recall can fall because of data or concept drift, bad upstream features,
  or a release regression. Weekly quality and fairness evaluations distinguish
  this outcome from a feature-distribution alert.

### Feature tests and comparison window

The baseline is the Lab 2 training-customer feature set, restricted to the 11
numeric columns the endpoint receives and ordered as in
`monitoring/evidently_drift.py`. It excludes `customer_id`, `loyalty_tier`,
`churn_risk_score`, and `churn_label`. Compare one **champion** variant window
with that fixed training reference; use at least 500 distinct captured rows
after removing byte-identical test payloads. Review drift daily and after each
major promotion or catalog refresh. PSI is a rising distance statistic; KS is a
falling p-value.

| Endpoint feature | Test | Drift threshold | Reason |
|---|---|---:|---|
| `days_since_last_purchase` | PSI | > 0.20 | Recency shifts quickly during campaign and holiday cycles |
| `purchase_frequency_30d` | PSI | > 0.20 | Short-window purchase behavior is promotion-sensitive |
| `avg_order_value` | PSI | > 0.20 | Detects discounting and catalog price-mix changes |
| `category_diversity_score` | KS | p < 0.05 | Detects a distribution change from catalog refreshes |
| `total_spend_90d` | KS | p < 0.05 | Detects a broader spend-distribution shift |

These five thresholds are the `DRIFT_PLAN` in the processing script. The PSI
comparison is `value > threshold`; the KS comparison is `value < threshold`.
The 500-row minimum is a quality gate: an underpowered report is not evidence
of drift or evidence of health.

### Concept-drift proxy and label lag

The true churn label is not known until the complete 90-day holdout window
closes, so a prediction made today cannot be scored against ground truth for
three months. Until then, track the share of scored customers who make a
purchase or redeem a retention offer within 14 days of the scored campaign.
This early-response proxy is available within **14 days** and can flag a sudden
change in customer response, but it does not replace the 90-day churn label.
At day 90, join outcomes back to the original prediction cohort and calculate
recall@10 and fairness by loyalty tier; compare proxy alerts with the matured
labels to recalibrate the proxy.

## SLOs and error budgets

Measure availability and latency over a rolling 30-day window. A 30-day month
contains 43,200 minutes. `ModelLatency` is recorded in microseconds; the 20 ms
SLO bound is `20000`, the Task 1 200 ms alert is `200000`, and the runbook's
500 ms incident threshold is `500000`.

| SLO | Target and SLI (good / total) | Error budget | Deployment freeze trigger |
|---|---|---|---|
| Availability | 99.5% successful predictions / all requests | 0.5% bad events: 216 minutes per 30-day month, or 5,000 failed requests per 1,000,000 requests | Freeze model and infrastructure changes if availability is below 99.5% for a rolling 30 days or more than 50% of the monthly failed-request budget is spent in any rolling 7 days |
| Latency | At least 95% of requests complete in <20 ms (`ModelLatency` ≤ 20000 µs) | 5% slow requests: 50,000 per 1,000,000 requests in the rolling 30-day window | Freeze releases if the rolling 7-day p95 exceeds 20000 µs or more than 50% of the monthly slow-request budget is spent in 7 days |
| Prediction quality | Weekly holdout recall@10% ≥ 0.25 | At most 1 failed weekly sample in a rolling 13-week quarter (12 of 13 samples must pass) | Freeze model promotion if a matured weekly sample is below 0.25 or if two consecutive weekly samples are missing |
| Fairness | Weekly recall@10% gap across loyalty tiers ≤ 10 percentage points | At most 1 breached weekly evaluation in a rolling 13-week quarter | Freeze model promotion if any adequately sized tier gap exceeds 10 pp; resume only after a passing evaluation and model-owner review |

For quality and fairness, a weekly sample is adequate only when each compared
loyalty tier has at least 20 positive and 20 negative outcomes. Mark a small
sample inconclusive and collect another window; do not call it a pass.

## Runbook: Data drift detected

### Detection

- Alert: `northstar-model-drift`, when an adequately powered Evidently report
  finds drift on any planned feature (PSI value > its threshold or KS p-value <
  its threshold).
- Confirm with `monitoring/reports/drift_report.json` and
  `drift_violations.json`; check `captured_records` ≥ 500 and
  `underpowered_window` is `false`.
- Secondary signals: input capture volume, the `ChurnAlertVolume` trend, recent
  catalog/promotion changes, and weekly recall/fairness results.

### Triage (< 5 minutes)

- Step 1: Check the report's feature, test direction, threshold, baseline row
  count, capture row count, and variant. Verify PSI uses `>` and KS uses `<`.
- Step 2: Compare the feature's recent values with the release, catalog, and
  promotion calendar; confirm capture includes one record per request and that
  repeated smoke-test payloads were deduplicated.

### Containment Options

- Option A: If drift is limited to canary traffic or started with a release,
  set canary weight to zero using the Lab 5 rollback action and keep the
  champion serving while the owner investigates.
- Option B: If drift is broad but predictions remain available, pause model
  promotion and use the approved conservative retention offer policy while
  retaining the incumbent model. Do not retrain on an unreviewed drift window.

### Escalation

- Escalate if the same feature breaches on two consecutive daily windows, if
  two or more features breach once, or if weekly recall falls below 0.25.
- Page the ML engineer on-call and notify the model owner and retention product
  owner.
- Response SLA: acknowledge within 15 minutes; name an incident lead within
  30 minutes if containment is still active.

### Resolution Verification

- Run Evidently on a fresh ≥500-distinct-row champion window after the
  corrective action; confirm the affected feature is below its threshold and
  `underpowered_window` is `false`.
- Confirm `northstar-model-drift` returns to `OK` after its next valid metric
  evaluation and inspect the next weekly recall@10 sample.

### Post-Incident Actions

- Within 24 hours, record the triggering feature values, campaign/catalog
  context, containment, and whether the baseline needs an approved refresh.
- Postmortem required if drift persists for two daily windows, affects two or
  more features, or causes a quality/fairness SLO breach; otherwise document
  the incident ticket and owner decision.

## Runbook: Inference latency spike

### Detection

- Alert: `northstar-inference-latency` at champion p95 > 200000 µs for 3 of 5
  one-minute periods. Start this runbook immediately if p95 exceeds 500000 µs
  for more than 5 minutes.
- Secondary signals: `Invocation5XXErrors`, CPU and memory utilization, live
  request rate, variant weights, and the latest endpoint deployment time.

### Triage (< 5 minutes)

- Step 1: Query `AWS/SageMaker` `ModelLatency` with endpoint and variant
  dimensions using extended statistics (`p50`, `p95`, `p99`); verify values are
  microseconds and compare champion with canary.
- Step 2: Check endpoint status, CPU/memory, invocation errors, request rate,
  and whether the spike began during a rollout or cold start. A single warm-up
  sample near 24000 µs is not a sustained 200 ms breach.

### Containment Options

- Option A: If canary latency is elevated or the spike started at rollout,
  immediately set canary weight to zero with the Lab 5 rollback action; retain
  the healthy champion.
- Option B: If both variants are slow or the endpoint cannot recover quickly,
  serve a cached last-known-safe score when available; otherwise use a
  conservative rules-based offer policy and queue non-urgent scoring for
  retry. Do not block the customer interaction on model inference.

### Escalation

- Escalate if champion p95 remains above 500000 µs for 5 minutes, 5xx exceeds
  5% for 5 minutes, or containment does not restore p95 below 200000 µs within
  10 minutes.
- Page the ML engineer on-call and service/release operator; page the service
  manager if both variants are unavailable.
- Response SLA: acknowledge within 5 minutes for the >500 ms condition and
  provide an update within 15 minutes.

### Resolution Verification

- Confirm the endpoint is `InService`, the canary weight matches the intended
  release state, and p95 is below 200000 µs for 10 consecutive minutes.
- Confirm `northstar-inference-latency` is `OK` and 5xx errors are below 1%
  over the same 10-minute window.

### Post-Incident Actions

- Within 24 hours, attach latency percentiles, variant weights, CPU/memory,
  request volume, deployment events, and rollback times to the incident ticket.
- Postmortem required if p95 exceeded 500000 µs for 5 minutes, more than 5%
  of requests failed, customer interactions used the fallback, or an SLO budget
  was exhausted; otherwise record the owner review and corrective task.
