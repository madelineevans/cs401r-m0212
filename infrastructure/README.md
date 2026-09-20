# infrastructure/ — Lab 1 Part B Terraform modules

Terraform implementation for Task B1. The four reusable modules are wired
into the AWS `dev` environment and the VPC, storage, and IAM modules are also
used by the LocalStack `local` environment.

Verify the implementation:

```bash
cd environments/dev
terraform init
terraform fmt -check -recursive ../..   # no output = pass
terraform validate                      # exits 0
```

Both must still pass when you submit — that is 5 of the 15 points in B1.

## Layout

```
modules/vpc/        aws_vpc, aws_subnet (public only), aws_internet_gateway,
                    aws_route_table, aws_route_table_association, aws_security_group
modules/storage/    aws_s3_bucket + public_access_block, versioning,
                    server_side_encryption_configuration, aws_s3_object x4
modules/iam/        one aws_iam_role (MLEngineer trust), one aws_iam_policy,
                    one aws_iam_role_policy_attachment
modules/sagemaker/  aws_sagemaker_domain, aws_sagemaker_user_profile
```

Each module contains **only** its designated resources — that is graded.

## The rule that catches people

**No hardcoded names.** The rubric runs:

```bash
grep -rn '"northstar-dev"' infrastructure/modules/
```

and expects nothing. Build names from `var.project` and `var.environment`,
and give every variable a `description` — that is also graded.

The data bucket is the one name that also needs the account ID, because S3
bucket names are global and thirty students deploy this same code. Read it
from the caller inside `modules/storage`:

```hcl
data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.project}-${var.environment}-data-${data.aws_caller_identity.current.account_id}"
}
```

The same line yields `northstar-dev-data-<your account>` on AWS and
`northstar-local-data-000000000000` on LocalStack with no special-casing.
