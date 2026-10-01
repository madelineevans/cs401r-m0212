output "feature_group_name" {
  description = "SageMaker Feature Group name"
  value       = aws_sagemaker_feature_group.this.feature_group_name
}

output "feature_group_arn" {
  description = "SageMaker Feature Group ARN"
  value       = aws_sagemaker_feature_group.this.arn
}
