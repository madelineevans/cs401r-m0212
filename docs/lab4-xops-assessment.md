# Lab 4 — XOps Maturity Assessment

## Pipeline Stage Mapping

| Logical phase | Implementation |
|---|---|
| Source | CodePipeline `GitHubSource` uses the available `401r-Lab4` GitHub CodeConnections connection in us-east-1. A V2 push trigger filtered to `main` was verified by the WebhookV2 run for commit `32a2b35`. |
| Test | CodeBuild `PRE_BUILD` installs requirements and runs the repository pytest suites. A failed test exits before training or registration. |
| Build | CodeBuild stages the commit-specific Parquet training input and invokes the SageMaker churn pipeline. SageMaker trains with managed spot capacity. |
| Evaluate | The trainer writes evaluation metrics; CodeBuild enforces precision@10 ≥ 0.50, recall@10 ≥ 0.25, and positive 95% AUC lift confidence interval. Fairness gaps over 10 percentage points warn without blocking. |
| Register | A passing candidate is registered in SageMaker Model Registry as `PendingManualApproval`. CodePipeline then waits for a human approval action. |

## Champion-Challenger

The newest `Approved` package is the champion. Approve a candidate only when its AUC is no more than 0.02 below the champion AUC and all absolute evaluation gates pass: precision@10 ≥ 0.50, recall@10 ≥ 0.25, and the 95% confidence interval for AUC lift over the recency baseline excludes zero. Otherwise, reject the candidate. This is a binary promotion rule; the champion comparison reports the champion version and both AUC values in the build warning summary.

## Retraining Triggers

**Scheduled trigger (proposed):** an Amazon EventBridge Scheduler schedule starts the SageMaker Pipeline weekly, giving the model a regular refresh cadence. **Performance trigger (proposed):** SageMaker Model Monitor records feature or model-quality drift; a CloudWatch alarm on the monitor metric invokes an EventBridge rule that starts the SageMaker Pipeline. These triggers are documented designs, not deployed resources in this lab environment.

## DataOps Maturity

**Current level: 2/4.** This repository has distinct raw, processed, and customer-feature outputs, with automated checks for schemas, transaction grain, leakage, feature bounds, freshness, and consistency. `tests/test_data.py` contains 28 passing checks on the refreshed data, and `tests/test_features.py` has 19 passing unit and edge-case checks. The CI build uses root Parquet files from the feature output, stages them under a commit-specific S3 prefix, and passes that exact location to training. The registered candidate also records the training-data S3 URI, source-data timestamp, full code SHA, and evaluation-metrics URI in SageMaker package metadata. These controls make a run repeatable and give reviewers evidence about which data and code produced a model.

**Gap to Level 3:** data checks validate a batch snapshot and freshness at build time; they do not continuously detect changes in distributions, schema drift, or a missed upstream feature refresh. **Top priority investment:** add AWS Glue Data Quality rules to the feature job, publish rule outcomes and freshness to CloudWatch, and alert on failed or stale outputs before CodeBuild starts training. This would turn data checks into an operational signal with an owner and a response path.

## MLOps Maturity

**Current level: 2/4.** Training is implemented behind a stable `train(df, seed=42)` contract and runs through a SageMaker Pipeline using managed spot capacity. The CI job tests the model interface, evaluates precision and recall at the top 10%, and requires the 95% AUC-lift interval over a recency baseline to exclude zero. Fairness checks report loyalty-tier recall gaps as warnings. Passing models are versioned in SageMaker Model Registry as pending approval; approved package v5 now provides a champion for the regression gate. Four finished MLflow App runs preserve earlier experiments with different hyperparameters and metrics.

**Gap to Level 3:** reliable, monitored automation after registration is not complete. Model promotion still requires a person, and production drift monitoring and automatic retraining are proposals rather than deployed controls. **Top priority investment:** add SageMaker Model Monitor with CloudWatch alarms, then connect a weekly EventBridge schedule and a monitor-driven EventBridge rule to the SageMaker Pipeline. Keep registry approval as the deployment gate until monitoring and rollback behavior are demonstrated.
