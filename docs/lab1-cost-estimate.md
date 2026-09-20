# Lab 1 Cost Estimate

This estimate assumes the environment is used for short lab sessions, Studio
kernels are shut down after use, and the Terraform stack is destroyed when the
evidence is captured. Prices vary by account, region, credits, and AWS pricing
changes; this is a planning estimate rather than a bill.

| Resource | Cost driver | Lab 1 estimate |
| --- | --- | ---: |
| VPC, subnet, route table, internet gateway, security group | No hourly charge for these resources | $0 |
| S3 bucket | Four zero-byte prefix objects and negligible storage | <$0.10 |
| IAM role and policy | No additional charge | $0 |
| SageMaker Domain | Domain control plane and small amount of attached storage | ~$1–3 |
| SageMaker Studio `ml.t3.medium` kernel | Approximately $0.05/hour while running | ~$0.50–2 |
| **Expected total** | Short session followed by shutdown and destroy | **~$2–5** |

The main cost-control action is to stop Studio applications immediately after
use. No endpoint, NAT gateway, or training job is part of this lab. The EFS
retention policy is set to `Delete` so the Domain teardown does not leave an
orphaned home filesystem generating storage charges.
