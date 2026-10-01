variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "bucket_name" {
  description = "S3 data bucket name"
  type        = string
}

variable "data_engineer_role_arn" {
  description = "ARN of the DataEngineer execution role"
  type        = string
}

variable "private_subnet_id" {
  description = "Private subnet for Glue workers"
  type        = string
}

variable "security_group_id" {
  description = "Security group for Glue workers"
  type        = string
}

variable "availability_zone" {
  description = "Availability Zone for the Glue network connection"
  type        = string
}

variable "transform_script_path" {
  description = "Local path to the transform Glue script"
  type        = string
}

variable "transform_script_key" {
  description = "S3 key for the transform Glue script"
  type        = string
  default     = "artifacts/glue/transform.py"
}

variable "feature_engineer_script_path" {
  description = "Local path to the feature engineering Glue script"
  type        = string
}

variable "feature_engineer_script_key" {
  description = "S3 key for the feature engineering Glue script"
  type        = string
  default     = "artifacts/glue/feature_engineer.py"
}

variable "feature_group_name" {
  description = "SageMaker Feature Group consumed by the feature engineering job"
  type        = string
}

variable "aws_region" {
  description = "AWS region used by the SageMaker Feature Store runtime client"
  type        = string
}
