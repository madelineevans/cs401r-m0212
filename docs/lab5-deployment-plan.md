# NorthStar Churn Model Deployment Plan

## 1. Deployment strategy and rationale

Use a real-time SageMaker endpoint with a 90/10 canary because NorthStar makes retention decisions for individual customers during interactions; nightly batch scores could be stale. Version 4 is the incumbent champion and version 10 is the candidate canary. Start on `ml.t2.medium` to capture the expected scaling rejection, then use `ml.m5.large` because burstable variants cannot be Application Auto Scaling targets.

## 2. Pre-deployment checklist

Run these commands from the repository root in Bash. Use the `MaeAdmin` AWS profile for account `722160254691` in `us-east-1`:

```bash
export AWS_PROFILE=MaeAdmin
export AWS_DEFAULT_REGION=us-east-1
export AWS_REGION=us-east-1
export ACCOUNT_ID=722160254691
export ENDPOINT=northstar-churn-prod
export BUCKET=northstar-dev-data-${ACCOUNT_ID}
```

The release operator confirms both registry packages are approved and their S3 model objects exist:

```bash
aws sagemaker describe-model-package --model-package-name arn:aws:sagemaker:us-east-1:${ACCOUNT_ID}:model-package/northstar-churn-models/4 --query ModelApprovalStatus --output text
aws sagemaker describe-model-package --model-package-name arn:aws:sagemaker:us-east-1:${ACCOUNT_ID}:model-package/northstar-churn-models/10 --query ModelApprovalStatus --output text
aws s3api head-object --bucket ${BUCKET} --key artifacts/models/churn/20261013T040651Z/model.tar.gz
aws s3api head-object --bucket ${BUCKET} --key artifacts/training/pipelines-a0ajt1k9nsg6-TrainChurnModel-rooLcNb0FK/output/model.tar.gz
```

The NorthStar model owner (`MaeAdmin`) reviewed the validation metrics and slice results, then approved versions 4 and 10 in SageMaker Model Registry. Version 4 has AUC-ROC 0.7819, precision@top10 0.7167, and recall@top10 0.3258. Version 10 has AUC-ROC 0.7835, precision@top10 0.7267, recall@top10 0.3303, and a positive lift confidence-interval low bound of 0.0427; its Gold, Silver, and Platinum slice AUCs are flagged below aggregate. The release operator confirms `ml.m5.large` endpoint quota is at least two; the current account value is 30. Confirm `deployment/configs/sample.csv` contains one headerless row in `FEATURE_COLUMNS` order. Notify the retention owner, ML engineer on call, and security reviewer before creating resources.

Create the two SageMaker models from the approved packages, then deploy the temporary t2 configuration and update it to the final m5 configuration:

```bash
aws sagemaker create-model --model-name northstar-churn-model-v4 --execution-role-arn arn:aws:iam::${ACCOUNT_ID}:role/northstar-dev-MLEngineer --primary-container '{"ModelPackageName":"arn:aws:sagemaker:us-east-1:'"${ACCOUNT_ID}"':model-package/northstar-churn-models/4"}'
aws sagemaker create-model --model-name northstar-churn-model-v10 --execution-role-arn arn:aws:iam::${ACCOUNT_ID}:role/northstar-dev-MLEngineer --primary-container '{"ModelPackageName":"arn:aws:sagemaker:us-east-1:'"${ACCOUNT_ID}"':model-package/northstar-churn-models/10"}'
aws sagemaker create-endpoint-config --cli-input-json file://deployment/configs/endpoint-config-t2-demo.json
aws sagemaker create-endpoint --endpoint-name ${ENDPOINT} --endpoint-config-name northstar-churn-prod-t2-demo
aws sagemaker wait endpoint-in-service --endpoint-name ${ENDPOINT}
aws application-autoscaling register-scalable-target --cli-input-json file://deployment/configs/scalable-target.json
aws sagemaker update-endpoint --endpoint-name ${ENDPOINT} --endpoint-config-name northstar-churn-prod-canary
aws sagemaker wait endpoint-in-service --endpoint-name ${ENDPOINT}
aws application-autoscaling register-scalable-target --cli-input-json file://deployment/configs/scalable-target.json
aws application-autoscaling put-scaling-policy --cli-input-json file://deployment/configs/scaling-policy.json
aws cloudwatch put-metric-alarm --cli-input-json file://deployment/configs/rollback-alarm.json
```

## 3. Rollback criteria

CloudWatch alarm `northstar-churn-rollback-latency` watches the canary’s `AWS/SageMaker` `ModelLatency` metric using p95. ModelLatency is measured in microseconds. Roll back when p95 exceeds **200000 microseconds (200 ms) for two consecutive 60-second periods**. The ML engineer on call reviews the alarm and owns the rollback decision; the release operator executes `bash deployment/configs/rollback-action.sh`. That action sets canary weight to zero and champion weight to one. Wait for `InService`, then confirm the endpoint weights and invoke the endpoint 100 times; zero calls should reach the canary. The alarm threshold and dimensions are stored in `deployment/configs/rollback-alarm.json`.

## 4. Monitoring window

Production uses a 48-hour canary before promotion. The lab observes for 60 minutes to limit endpoint charges. The final m5 endpoint entered `InService` at 17:09:54 Mountain time on Nov 14, 2026; rollback followed the 18:09:54 observation end. This compression cannot reveal day/night traffic patterns, weekly customer behavior, or infrequent failures. In production also monitor request volume, p95 latency, 5xx and invocation errors, variant traffic, score distributions, and capture delivery. The initial 200-call t2 run observed 181 champion and 19 canary responses. Direct smoke calls to both m5 variants succeeded; canary p95 was 24488 microseconds and the alarm remained `OK`. S3 data-capture files were observed. The post-rollback 100-call check returned champion 100 and canary 0; teardown verified zero endpoints, endpoint configs, and scaling targets. Target tracking uses 1000 invocations per instance, 60-second scale-out and 600-second scale-in cooldowns. The t2 rejection and m5 quota-backed endpoint are recorded.

Count actual variant responses for 200 calls:

```bash
counts=(); for i in $(seq 1 200); do v=$(aws sagemaker-runtime invoke-endpoint --endpoint-name "$ENDPOINT" --content-type text/csv --body fileb://deployment/configs/sample.csv /tmp/lab5-response.csv --query InvokedProductionVariant --output text); counts+=("$v"); done; printf '%s\n' "${counts[@]}" | sort | uniq -c
```

## 5. Stakeholder notifications

At deployment start, the release operator tells the retention product owner, ML engineer on call, and security reviewer the package versions, endpoint name, 90/10 split, rollback threshold, and observation start time. At promotion, the operator sends the model owner and retention owner the observed traffic counts, alarm state, validation summary, and promotion time. On rollback, the on-call engineer immediately notifies the release operator, model owner, retention owner, and security reviewer with the triggering metric and value, the new weights, and the incident ticket reference.

## 6. Post-deployment review

Within one business day, the model owner, release operator, on-call engineer, retention owner, and security reviewer review metrics, traffic split, alarm, capture, and teardown evidence. Record the decision, risks, follow-up owners, and next steps in `docs/lab5-deployment-output.txt` and update registry notes. Promotion requires model-owner sign-off.

## 7. Resource cleanup

After the observation and rollback evidence are captured, run `bash scripts/teardown-lab5.sh` from the repository root. The script removes scaling policies and targets, rollback alarms, the endpoint, endpoint configurations, and SageMaker models. Do not stop after setting canary weight to zero: provisioned endpoint instances continue billing. Confirm `docs/lab5-teardown-output.txt` reports `OK` for each check, then append the final live API counts to `docs/lab5-deployment-output.txt`:

```bash
aws sagemaker list-endpoints --query 'length(Endpoints)' --output text
aws sagemaker list-endpoint-configs --query 'length(EndpointConfigs)' --output text
aws application-autoscaling describe-scalable-targets --service-namespace sagemaker --query 'length(ScalableTargets)' --output text
```

All three counts must be zero. Commit the deployment plan, config files, CLI evidence, and teardown output, then tag the reviewed commit `lab5-submit` and push `main` and that tag.
