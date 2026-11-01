# Lab 4 — XOps Maturity Assessment

## Pipeline Stage Mapping

| Phase | Implementation and evidence |
|---|---|
| Source | CodePipeline V2 uses the available `401r-Lab4` GitHub connection. Push commit `32a2b35` triggered `WebhookV2` on `main`. |
| Test | CodeBuild runs pytest in `PRE_BUILD`; the deliberate failure stopped before training or registration and triggered the alarm email. |
| Build | CodeBuild stages commit-specific feature Parquet data in S3 and starts the SageMaker Pipeline, which trains using managed spot capacity. |
| Evaluate | Gates require precision@10 ≥ 0.50, recall@10 ≥ 0.25, and a 95% AUC-lift interval excluding zero. Fairness gaps above 10 percentage points warn without blocking. |
| Register | Passing candidates enter SageMaker Model Registry as `PendingManualApproval`; CodePipeline’s separate metrics review action requires human approval. |

## Champion-Challenger

Compare each candidate with the newest `Approved` package. Approve only if candidate AUC ≥ champion AUC − 0.02 and all absolute gates pass; otherwise, reject it. The build warning records the champion version and both AUCs. v5 was champion in the final run; v9 passed the checks and awaits registry approval.

## Retraining Triggers

**Proposed schedule:** Amazon EventBridge Scheduler starts the SageMaker Pipeline weekly. **Proposed performance trigger:** if a rolling 7-day labeled production window has precision@10 < 0.50 or recall@10 < 0.25, SageMaker Model Monitor publishes the result, a CloudWatch alarm fires, and an EventBridge rule starts the pipeline. These are proposed, automatable triggers; neither is deployed in this lab.

## DataOps Maturity

**Current level: 2/4.** **Evidence:** the final `docs/lab4-build-green.log` shows 28 data checks and 19 feature tests passing. `tests/test_data.py` checks schema, transaction grain, leakage, freshness, and consistency; `tests/test_features.py` covers bounds and edge cases. `buildspec.yml` stages feature Parquet under a commit-specific S3 prefix. `docs/lab4-model-package.json` records that data URI and timestamp, source commit, and evaluation URI.

**Gap to Level 3:** checks cover batch snapshots but do not continuously detect distribution drift, schema changes, or missed feature refreshes. **Top priority investment:** add AWS Glue Data Quality rules to the feature job, publish outcomes and freshness to CloudWatch, and alert before training on stale or invalid outputs.

## MLOps Maturity

**Current level: 2/4.** **Evidence:** `models/churn/pipeline_definition.py` trains with managed spot capacity, while `buildspec.yml` runs tests and evaluation gates. `docs/lab4-build-green.log` records AUC 0.7835, precision@10 0.7267, recall@10 0.3303, a positive 95% lift interval, and the champion v5 comparison. `docs/lab4-model-package.json` records lineage metadata; `docs/lab4-mlflow-runs.txt` documents four distinct MLflow App runs. The push-triggered run registered v9 and its pipeline review succeeded.

**Gap to Level 3:** promotion remains manual, and production drift monitoring and automatic retraining are not deployed. **Top priority investment:** deploy SageMaker Model Monitor and CloudWatch alarms, then connect weekly and drift-driven EventBridge triggers. Keep registry approval as the deployment gate until monitoring and rollback are demonstrated.
