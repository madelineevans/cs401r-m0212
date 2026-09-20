# Task S2 — Monthly Cost Estimate

This estimate assumes the environment is used for short lab sessions, Studio
kernels are shut down after use, and the Terraform stack is destroyed when the
evidence is captured. Prices vary by account, region, credits, and AWS pricing
changes; this is a planning estimate rather than a bill.

| Component             | Monthly estimate | Key assumptions                                                                                                                 | One optimization                                                                                                                   |
| --------------------- | ---------------: | ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| SageMaker Studio      |        **$8.80** | One `ml.t3.medium` kernel at approximately $0.05/hour for 8 hrs/day for 22 weekdays a month                                     | Automatic shutdown reduces usage from about 730 to 176 hours/month changes the estimate from $36.50 to $8.80, saving $27.70/month. |
| S3 storage            |        **$0.23** | 10 GB in the `northstar-dev-data` bucket at $0.023/GB-month (S3 Standard, us-east-1)                                            | Lifecycle raw/processed data to S3 Standard-IA after 30 days; at this small size the savings are almost nothing though.            |
| Internet Gateway      |        **$0.20** | Internet Gateway has no hourly fee; budget 20 GB/month of internet-bound data transfer at the assignment assumption of $0.01/GB | Keep traffic to same-Region AWS services such as S3; this avoids unnecessary internet data transfer                                |
| DynamoDB (state lock) |        **$0.01** | On-demand table with approximately 100 state-lock reads and writes/month                                                        | Keep on-demand capacity instead of provisioning RCUs/WCUs for this low, irregular workload                                         |
| S3 state bucket       |        **$0.02** | 1 GB of Terraform state and retained versions at $0.023/GB-month                                                                | Add lifecycle expiration for old state versions                                                                                    |
| **Total**             |        **$9.26** | Sum of the five monthly estimates                                                                                               | The Studio idle-shutdown change lowers the cost the most                                                                           |
