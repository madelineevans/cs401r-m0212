#!/usr/bin/env bash
set -euo pipefail

aws sagemaker update-endpoint-weights-and-capacities \
  --endpoint-name northstar-churn-prod \
  --desired-weights VariantName=champion,DesiredWeight=1.0 VariantName=canary,DesiredWeight=0.0 \
  --region us-east-1
