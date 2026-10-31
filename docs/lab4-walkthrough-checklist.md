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
- [x] Deployed `northstar-cicd`. The first run exposed a malformed nested Feature Store marker key; the second run used the curated commit-specific Parquet prefix and training succeeded. Registration then exposed missing scoped Model Registry permissions on `MLEngineer`; the Terraform policy is now updated and applied.
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
- [ ] Confirm the SageMaker pipeline/model package group can be upserted.

## 3. CI/CD pipeline and failure demonstration (30 points)

- [ ] Document the five logical phases in order: Source → Test → Build → Evaluate → Register. The reference CodePipeline has Source, Build, and ManualApproval stages; map phases to stages rather than creating one stage per phase.
- [x] Pushed the initial Lab 4 implementation to `main` before deploying `pipeline.yaml`; stack creation triggered a run immediately.
- [ ] After the training-input fix is pushed, obtain a green run that trains through `churn_model.train()`, passes gates, and registers a `PendingManualApproval` package. The stack was deployed with `CAPABILITY_NAMED_IAM`.
- [ ] Approve the first green package so the champion regression test can compare against it on the later green run.
- [ ] Confirm the failure alarm starts in OK; record the BEFORE snapshot.
- [ ] Push a deliberately failing test. Confirm failure in `PRE_BUILD`, no model registration, alarm state ALARM, successful SNS action, and delivery to a confirmed subscription.
- [ ] Save the failed build log and received alarm email screenshot (showing received time); record AFTER FAILED RUN.
- [ ] Revert the deliberate test and push. Confirm the build succeeds, alarm returns to OK, and the newest package is `PendingManualApproval`; record AFTER REVERT.
- [ ] Keep both the failure commit and revert in `main` history.

## 4. MLOps configuration and maturity assessment (40 points)

- [ ] Create/update `docs/lab4-xops-assessment.md` with `## Pipeline Stage Mapping`.
- [ ] Add `## Champion-Challenger` with a numeric, binary replacement criterion.
- [ ] Add `## Retraining Triggers` with an automatable schedule and an automatable performance trigger; name the AWS service for each.
- [ ] Produce at least three MLflow App runs with differing hyperparameters and logged metrics. Save the full output and MLflow App tracking URI to `docs/lab4-mlflow-runs.txt`. SageMaker's auto-created pipeline Experiments do not count.
- [ ] Add training data S3 URI and timestamp, code commit SHA, and evaluation metrics to the final model package's customer metadata; save the full description as `docs/lab4-model-package.json`.
- [ ] Write about 400 words under `## DataOps Maturity` and `## MLOps Maturity`, each with current level, concrete repository evidence, a specific gap to the next level, and one actionable priority investment.

## 5. Capture evidence, teardown, and submit

Before deleting resources, save and review:

- [ ] `docs/lab4-build-green.log`
- [ ] `docs/lab4-build-failed.log`
- [ ] `docs/lab4-pipeline-runs.txt`
- [ ] `docs/lab4-failure-demo.txt`
- [ ] `docs/lab4-alarm-email.png`
- [ ] `docs/lab4-model-registry.json`
- [ ] `docs/lab4-model-package.json`
- [ ] `docs/lab4-mlflow-runs.txt`
- [ ] `docs/lab4-xops-assessment.md`

Then:

- [ ] Delete the CI CloudFormation stack before the final docs-only push so it does not start another training run.
- [ ] Empty and delete the versioned artifacts bucket; delete the CodeBuild log group; run Lab 2 teardown when finished.
- [ ] Before deleting the data bucket, reject any Approved model package that points to an artifact being deleted.
- [ ] Commit and push the work, tag the graded commit `lab4-submit`, push the tag, and submit the repository URL in Canvas.

The handout estimates about $0.02 per pipeline run and $0.045 per hour for the Lab 2 NAT Gateway. Keep infrastructure up only while collecting evidence that requires it.
