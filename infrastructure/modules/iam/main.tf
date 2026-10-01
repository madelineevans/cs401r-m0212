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
  bucket_arn  = "arn:${data.aws_partition.current.partition}:s3:::${local.bucket_name}"
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

resource "aws_iam_role" "data_engineer" {
  name = "${var.project}-${var.environment}-DataEngineer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = [
          "glue.amazonaws.com",
          "lambda.amazonaws.com",
          "sagemaker.amazonaws.com"
        ]
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "data_engineer" {
  name        = "${replace(title(var.project), "star", "Star")}DataEngineerPolicy"
  description = "Permissions for ${var.project} ${var.environment} data engineering workflows"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "GlueFullAccess"
        Effect   = "Allow"
        Action   = "glue:*"
        Resource = "*"
      },
      {
        Sid    = "GlueNetworkInterfaces"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs",
          "ec2:DescribeRouteTables",
          "ec2:DescribeAvailabilityZones"
        ]
        Resource = "*"
      },
      {
        Sid    = "TagGlueNetworkInterfaces"
        Effect = "Allow"
        Action = [
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "arn:${data.aws_partition.current.partition}:ec2:*:*:network-interface/*"
      },
      {
        Sid    = "ReadWriteDataPrefixes"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${local.bucket_arn}/raw/*",
          "${local.bucket_arn}/processed/*",
          "${local.bucket_arn}/features/*",
          "${local.bucket_arn}/features_$folder$"
        ]
      },
      {
        Sid    = "ReadGlueScripts"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${local.bucket_arn}/artifacts/glue/*"
      },
      # Glue's S3A connector performs an unqualified ListBucket call while
      # resolving prefixes. Keep object access scoped below; ListBucket itself
      # is metadata-only and is limited to the data bucket.
      {
        Sid      = "ListDataPrefixes"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = local.bucket_arn
      },
      {
        Sid    = "FeatureStoreOperations"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateFeatureGroup",
          "sagemaker:DescribeFeatureGroup",
          "sagemaker:PutRecord"
        ]
        Resource = "*"
      },
      {
        Sid    = "FeatureStoreBucketChecks"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:GetBucketAcl"
        ]
        Resource = local.bucket_arn
      },
      {
        Sid      = "FeatureStoreObjectAcl"
        Effect   = "Allow"
        Action   = "s3:PutObjectAcl"
        Resource = "${local.bucket_arn}/features/*"
      },
      {
        Sid    = "WriteGlueLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "data_engineer" {
  role       = aws_iam_role.data_engineer.name
  policy_arn = aws_iam_policy.data_engineer.arn
}

resource "aws_iam_role" "model_monitor" {
  name = "${var.project}-${var.environment}-ModelMonitor"

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

resource "aws_iam_policy" "model_monitor" {
  name        = "${replace(title(var.project), "star", "Star")}ModelMonitorPolicy"
  description = "Permissions for ${var.project} ${var.environment} model monitoring"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchMetricsAndAlarms"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:DescribeAlarms"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadDriftProcessingRuns"
        Effect = "Allow"
        Action = [
          "sagemaker:ListProcessingJobs",
          "sagemaker:DescribeProcessingJob"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadArtifacts"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${local.bucket_arn}/artifacts/*"
      },
      {
        Sid      = "ListArtifacts"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["artifacts/*"]
          }
        }
      },
      {
        Sid    = "WriteMonitorLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "model_monitor" {
  role       = aws_iam_role.model_monitor.name
  policy_arn = aws_iam_policy.model_monitor.arn
}
