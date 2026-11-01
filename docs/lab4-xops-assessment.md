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

**Proposed schedule:** use Amazon EventBridge Scheduler to start the SageMaker Pipeline weekly. **Proposed performance trigger:** SageMaker Model Monitor measures drift; a CloudWatch alarm invokes an EventBridge rule that starts the pipeline. Neither trigger is deployed in this lab.

## DataOps Maturity

**Current level: 2/4.** The repository separates raw, processed, and customer-feature data. `tests/test_data.py` checks schema, transaction grain, leakage, freshness, and consistency; `tests/test_features.py` covers bounds and edge cases. CI stages feature Parquet under a commit-specific S3 prefix and trains from that location. Package metadata records the training URI and timestamp, source commit, and evaluation URI. The final CI run passed the suite.

**Gap to Level 3:** checks cover a batch snapshot, but do not continuously detect distribution drift, schema changes, or missed feature refreshes. **Priority:** add AWS Glue Data Quality rules to the feature job, publish outcomes and freshness to CloudWatch, and alert before training on stale or invalid outputs.

## MLOps Maturity

**Current level: 2/4.** SageMaker Pipeline trains the model using managed spot capacity. CI checks model behavior and metric gates; fairness gaps are warnings. Registry versions preserve candidates, and the champion regression test compares each with the latest approved model. Four MLflow App runs record experiments with distinct parameters and metrics. The final push-triggered run passed and registered v9; pipeline review succeeded.

**Gap to Level 3:** model promotion remains manual, and production drift monitoring and automatic retraining are not deployed. **Priority:** add SageMaker Model Monitor and CloudWatch alarms, then connect weekly and drift-driven EventBridge triggers to the pipeline. Keep registry approval as the deployment gate until monitoring and rollback are demonstrated.
