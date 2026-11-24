# Lab 6 monitoring workflow

1. Run `bash scripts/preflight-lab6.sh` before any billable resource work.
2. If the Lab 5 endpoint has no data capture, roll it with
   `deployment/configs/canary_deploy_realtime.py`. Keep the current
   `deployment/configs/sample.csv`; the instructor kit intentionally does not
   ship a replacement.
3. Export the Lab 2 training-customer features with
   `monitoring/build_baseline.py`, inspect the header and row count, then upload
   the CSV to `s3://<bucket>/monitoring/baseline/`.
4. After at least 500 distinct champion captures exist, run
   `monitoring/run_evidently_job.py`. Download the actual
   `drift_report.json` and `drift_violations.json` from that completed job into
   `monitoring/reports/`; do not synthesize report values.
5. Run `monitoring/publish_metrics.py` from the laptop after downloading the
   report. It publishes `DriftDetected` and the count of distinct daily
   champion scores at or above 0.5 as `ChurnAlertVolume`.
6. Run `python monitoring/deploy_dashboard.py`, inspect that each metric has
   live data, and capture evidence before teardown. The script creates
   `NorthStar-AI-Platform` and replaces the widget definition with the body
   returned by CloudWatch.
7. Finish the two-window evidence capture and teardown exactly as the Lab 6
   handout specifies. Keep account-specific CLI output as generated evidence.

The baseline in this repository was exported from the ignored Lab 2 feature
Parquet files using a temporary pandas/PyArrow runtime; no dependency was added
to the project requirements. Never substitute the one-row deployment smoke-test
payload for the training baseline.

## Account recovery note

The approved v10 registry entry in account 722 referenced an S3 model archive
that had been removed with the Lab 2 bucket. The archive could not be used by
SageMaker. The Lab 5-approved v4 package referenced the tracked
`model/model.tar.gz`; its training timestamp and model metadata matched that
package's original S3 key, so that exact file was restored there and used for
the monitored endpoint. Both traffic variants therefore exercised v4 during
this recovery session.
