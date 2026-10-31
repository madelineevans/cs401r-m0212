# Lab 4 Walkthrough Checklist

Use this as the running checklist while completing Lab 4. Mark an item complete only after its code, run, or evidence has been checked. Work through one section at a time; do not start AWS resources until the local training code is ready and the spot quota has been confirmed.

## Current checkpoint

- [x] Lab 4 starter files are in the Lab 1–3 repository.
- [x] Python environment selected: `cs401r-lab3` with Python 3.11.17.
- [x] `tests/test_features.py`: 19 passed, including the explicit single-transaction edge case.
- [x] Reviewed the four test files against the Task 1 categories; all four files and their main test areas are present.
- [x] All four rubric test files have now been run against refreshed local data and current evaluation metrics: `test_features.py` 19 passed; `test_data.py` 28 passed; `test_model.py` plus `test_fairness.py` 22 passed, 1 skipped.
- [x] `tests/test_model.py` now passes the metric gates with generated evaluation metrics. The champion comparison is skipped until an Approved package exists, then must pass on a later green pipeline run.
- [x] With the new local model and real evaluation metrics, `tests/test_model.py tests/test_fairness.py` reported 22 passed and 1 skipped (no Approved champion). The fairness check emitted its expected 34.8-point warning; the recency monotonicity test was removed as outside the rubric.
- [x] Feature-suite requirement: explicit single-transaction test added and confirmed passing.
- [x] `models/churn/churn_model.py` ran locally on 9,999 rows; precision@top-10 0.7167, recall@top-10 0.3258, AUC 0.7819, and AUC-lift 95% CI [0.0404, 0.0767].
- [x] Local `evaluation_metrics.json` contains `slice_results`; the largest loyalty-tier recall gap is about 34.8 percentage points, which should produce the required non-blocking fairness warning.
- [x] Existing feature data is available in `s3://northstar-dev-data-722160254691/features/customers/`.
- [x] Existing feature files were copied to a temporary local channel for a preliminary trainer run. One timestamped offline-store `.txt` marker failed to copy because Windows disallows `:` in filenames; the trainer reads Parquet/CSV and ignores that marker.
- [x] Lab 2 infrastructure is restored; Terraform plan is clean. Feature job succeeded on 2026-10-31, and refreshed raw, processed, and root feature files are downloaded into gitignored `data/` folders.
- [x] `ml.m5.large` spot-training quota is now 4 in `us-east-1`.
- [x] Created the separate CI artifacts bucket with versioning, encryption, and public access blocked; GitHub connection is `AVAILABLE`.
- [x] Deployed `northstar-cicd`. The first run exposed a malformed nested Feature Store marker key; the second run used the curated commit-specific Parquet prefix and training succeeded. Registration then exposed missing scoped Model Registry permissions on `MLEngineer`; the Terraform policy is now updated and applied. A third manual run on `cdcb7827` passed training, registration, and CodeBuild gates; package v5 and the CodePipeline approval action are now approved.
- [ ] Automatic push trigger still needs verification: explicit V2 `GitHubSource` push trigger for `main` is deployed and appears in `get-pipeline`, but push `4c1062f` did not start an execution. The deliberate-failure push will test it again.
- [x] Local `tests/test_data.py` run against refreshed outputs: 28 passed, including schema, transaction grain, leakage, bounds, freshness under 48 hours, and consistency checks.

## 1. Finish Task 1 and local model implementation

### Test suite (30 points)

- [x] `tests/test_data.py`: raw, processed, and feature schemas; transaction-level grain; leakage check; bounded features; monotonic frequency windows; event freshness under 48 hours. Current run: 28 passed; missing required data fails rather than skips.
- [x] `tests/test_features.py`: at least five unit tests, including normal, zero-purchase, and single-transaction cases. Current run: 19 passed.
- [x] `tests/test_model.py`: precision@top-10 ≥ 0.50, recall@top-10 ≥ 0.25, 95% CI for model AUC minus recency baseline excludes zero, champion AUC no worse than champion minus 0.02, and valid probability outputs. Current local run passed; no absolute AUC threshold is imposed.
- [x] Champion regression test retrieves the newest Approved package's AUC and emits the required `warnings.warn(...)` line before asserting. Local run skips only because no Approved package exists yet; confirm it passes against an Approved champion in a later pipeline run.
- [x] `tests/test_fairness.py`: evaluates held-out recall by loyalty tier and warns when the gap exceeds 10 percentage points; warning is non-blocking. Current run emitted the 34.8-point warning and passed.
- [x] Removed the extra recency-monotonicity check: it is not part of Lab 3 training/evaluation logic or the Lab 4 model rubric. Kept the Lab 3 trainer unchanged; local model/fairness suite passed afterward.

### Lab 4 training contract

- [x] Implement `train(df, seed=42)` in `models/churn/churn_model.py` using the Lab 3 preprocessing, train/validation split, XGBoost training, recency-only baseline, and evaluation.
- [x] Return an `xgboost.Booster` and metrics including `precision_top10`, `recall_top10`, `baseline_auc_roc`, `lift_ci_low`, and `lift_ci_high`; include per-tier results for fairness review. The local SageMaker adapter run completed and wrote these outputs.
- [ ] Keep training code in `models/churn/`; do not import the Lab 3 script or add top-level `mlflow`/`sagemaker` imports.
- [x] Run the model and fairness tests with the generated model and evaluation metrics paths. Result: 22 passed, 1 skipped for no Approved champion; fairness warning appeared.

## 2. Prepare AWS prerequisites (no training until quota is confirmed)

- [x] Recheck `ml.m5.large` spot-training quota in `us-east-1`; it is 4.
- [x] Confirm Lab 2 infrastructure is up and the feature job has run within 48 hours. The restored feature job succeeded on 2026-10-31; raw, processed, and feature outputs are fresh.
- [x] Create a separate CodePipeline artifacts S3 bucket with versioning, AES256 encryption, and public access blocked. Bucket: `northstar-dev-cicd-artifacts-722160254691`; do not use the Lab 2 data bucket for CodePipeline artifacts.
- [x] Authorize the GitHub CodeConnections connection in the AWS console; AWS confirms status `AVAILABLE`. Connection ARN: `arn:aws:codeconnections:us-east-1:722160254691:connection/4f451362-5f95-4943-8a9f-cb5d5d86a189`.
- [x] MLEngineer policy source confirms constrained `iam:PassRole` to itself and includes `sagemaker:AddTags` and `sagemaker:ListTags`.
- [x] Confirm the SageMaker pipeline and `northstar-churn-models` package group can be upserted; the third run trained and registered package v5.

## 3. CI/CD pipeline and failure demonstration (30 points)

- [ ] Document the five logical phases in order: Source → Test → Build → Evaluate → Register. The reference CodePipeline has Source, Build, and ManualApproval stages; map phases to stages rather than creating one stage per phase.
- [x] Pushed the initial Lab 4 implementation to `main` before deploying `pipeline.yaml`; stack creation triggered a run immediately.
- [x] After the training-input and IAM fixes were pushed, a green run trained through `churn_model.train()`, passed the metric/fairness gates, and registered version 5. Package v5 is Approved and serves as champion.
- [x] Set model package v5 to `Approved` in SageMaker Model Registry. AWS confirms it can serve as the champion for the later regression check.
- [x] Later green run on commit `4c1062f` passed the champion regression test: champion v5 AUC=0.7835, candidate AUC=0.7835. It registered package v6 as `PendingManualApproval`; the CodePipeline approval action succeeded.
- [x] Confirm failure alarm starts in OK; before snapshot recorded in `docs/lab4-pipeline-runs.txt`. SNS email subscription is confirmed.
- [x] Recovery run registered package v8 as `PendingManualApproval`; the CodePipeline approval action succeeded, while SageMaker registry approval remains separate.
- [x] Deliberate failure commit `470506f` failed in `PRE_BUILD`; no SageMaker run/package was started. Alarm entered ALARM and CloudWatch confirmed successful SNS publish to the confirmed subscription.
- [x] Save failed build excerpt in `docs/lab4-build-failed.log` and before/after details in `docs/lab4-failure-demo.txt`.
- [x] Save the received alarm email screenshot showing its received time to `docs/lab4-alarm-email.png` (received 4:00 PM).
- [x] Revert the deliberate test and push. Recovery commit `753a911` passed CodeBuild, the alarm returned to OK, and new package v8 is `PendingManualApproval`; recovery evidence is recorded.
- [ ] Keep both the failure commit and revert in `main` history.

## 4. MLOps configuration and maturity assessment (40 points)

- [x] Create `docs/lab4-xops-assessment.md` with `## Pipeline Stage Mapping`.
- [x] Add `## Champion-Challenger` with a numeric, binary replacement criterion.
- [x] Add `## Retraining Triggers` with an automatable schedule and an automatable performance trigger; name the AWS service for each. Both are clearly marked as proposals, not deployed.
- [x] Document four finished MLflow App runs with differing hyperparameters and metrics, including the App tracking URI, in `docs/lab4-mlflow-runs.txt`. These existing runs were created 2026-10-13; create new Lab 4-dated runs only if the instructor requires them.
- [x] Add training data S3 URI and timestamp, full code commit SHA, and evaluation metrics to approved package v5's customer metadata; save the full description as `docs/lab4-model-package.json`. Future builds now attach these fields in `post_build`.
- [ ] Review the ~400-word draft under `## DataOps Maturity` and `## MLOps Maturity`; personalize the maturity ratings and priorities.

## 5. Capture evidence, teardown, and submit

Before deleting resources, save and review:

- [x] `docs/lab4-build-green.log`
- [x] `docs/lab4-build-failed.log`
- [x] `docs/lab4-pipeline-runs.txt`
- [x] `docs/lab4-failure-demo.txt`
- [x] `docs/lab4-alarm-email.png`
- [x] `docs/lab4-model-registry.json`
- [x] `docs/lab4-model-package.json`
- [x] `docs/lab4-mlflow-runs.txt`
- [ ] `docs/lab4-xops-assessment.md`

Then:

- [ ] Delete the CI CloudFormation stack before the final docs-only push so it does not start another training run.
- [ ] Empty and delete the versioned artifacts bucket; delete the CodeBuild log group; run Lab 2 teardown when finished.
- [ ] Before deleting the data bucket, reject any Approved model package that points to an artifact being deleted.
- [ ] Commit and push the work, tag the graded commit `lab4-submit`, push the tag, and submit the repository URL in Canvas.

The handout estimates about $0.02 per pipeline run and $0.045 per hour for the Lab 2 NAT Gateway. Keep infrastructure up only while collecting evidence that requires it.
