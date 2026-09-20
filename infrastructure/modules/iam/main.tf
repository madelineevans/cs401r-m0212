# ── modules/iam ──────────────────────────────────────────────────────────────
# Required resources (Task B1). Exactly one of each:
#
#   aws_iam_role                     MLEngineer, trusted by sagemaker.amazonaws.com
#   aws_iam_policy
#   aws_iam_role_policy_attachment
#
# Least privilege is graded in later labs, so start narrow: grant only the S3
# prefixes and SageMaker actions this role actually needs. A wildcard policy
# here will cost you points in Lab 2.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  bucket_name = "${var.project}-${var.environment}-data-${data.aws_caller_identity.current.account_id}"
}

resource "aws_iam_role" "ml_engineer" {
  name = "${var.project}-${var.environment}-MLEngineer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "sagemaker.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "ml_engineer" {
  name        = "${replace(title(var.project), "star", "Star")}MLEngineerPolicy"
  description = "Permissions for ${var.project} ${var.environment} SageMaker training and model workflows"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SageMakerTrainingAndModelOperations"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob",
          "sagemaker:CreateModel",
          "sagemaker:CreateEndpointConfig",
          "sagemaker:CreateEndpoint",
          "sagemaker:DeleteEndpoint",
          "sagemaker:DeleteEndpointConfig",
          "sagemaker:DeleteModel",
          "sagemaker:DescribeEndpoint",
          "sagemaker:DescribeEndpointConfig",
          "sagemaker:DescribeModel",
          "sagemaker:DescribeTrainingJob",
          "sagemaker:InvokeEndpoint",
          "sagemaker:ListTrainingJobs",
          "sagemaker:StopTrainingJob",
          "sagemaker:AddTags",
          "sagemaker:ListTags"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadInputAndWriteArtifacts"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:s3:::${local.bucket_name}/features/*",
          "arn:${data.aws_partition.current.partition}:s3:::${local.bucket_name}/artifacts/*"
        ]
      },
      {
        Sid      = "ListApprovedPrefixes"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${local.bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = ["features/*", "artifacts/*"]
          }
        }
      },
      {
        Sid    = "PullContainerImages"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Sid    = "WriteTrainingLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Sid      = "PassExecutionRoleToSageMaker"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = aws_iam_role.ml_engineer.arn
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "sagemaker.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ml_engineer" {
  role       = aws_iam_role.ml_engineer.name
  policy_arn = aws_iam_policy.ml_engineer.arn
}
