variable "feature_group_name" {
  description = "SageMaker Feature Group name"
  type        = string
}

variable "data_engineer_role_arn" {
  description = "Data Engineer role used by SageMaker Feature Store"
  type        = string
}

variable "offline_store_s3_uri" {
  description = "S3 URI for the Feature Store offline store"
  type        = string
}
