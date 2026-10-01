locals {
  name_prefix           = "${var.project}-${var.environment}"
  catalog_database_name = "${var.project}_${var.environment}"
  raw_table_name        = "customers"
  crawler_name          = "${local.name_prefix}-raw-crawler"
  transform_job_name    = "${local.name_prefix}-transform"
  feature_job_name      = "${local.name_prefix}-feature-engineer"
  processed_output_path = "s3://${var.bucket_name}/processed/customers/"
  features_output_path  = "s3://${var.bucket_name}/features/customers/"
  raw_input_path        = "s3://${var.bucket_name}/raw/customers/"
}

resource "aws_s3_object" "transform_script" {
  bucket = var.bucket_name
  key    = var.transform_script_key
  source = var.transform_script_path
  etag   = filemd5(var.transform_script_path)
}

resource "aws_glue_catalog_database" "this" {
  name = local.catalog_database_name
}

resource "aws_glue_connection" "network" {
  name            = "${local.name_prefix}-network"
  connection_type = "NETWORK"

  physical_connection_requirements {
    availability_zone      = var.availability_zone
    security_group_id_list = [var.security_group_id]
    subnet_id              = var.private_subnet_id
  }
}

resource "aws_glue_crawler" "raw" {
  name          = local.crawler_name
  role          = var.data_engineer_role_arn
  database_name = aws_glue_catalog_database.this.name

  s3_target {
    path = local.raw_input_path
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }
}

resource "aws_glue_job" "transform" {
  name              = local.transform_job_name
  role_arn          = var.data_engineer_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  max_retries       = 0
  timeout           = 60

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/${var.transform_script_key}"
  }

  connections = [aws_glue_connection.network.name]

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--job-language"            = "python"
    "--enable-glue-datacatalog" = "true"
    "--enable-metrics"          = "true"
    "--database_name"           = aws_glue_catalog_database.this.name
    "--table_name"              = local.raw_table_name
    "--output_path"             = local.processed_output_path
    "--TempDir"                 = "s3://${var.bucket_name}/artifacts/glue/temp/"
  }

  depends_on = [aws_s3_object.transform_script]
}

resource "aws_s3_object" "feature_engineer_script" {
  bucket = var.bucket_name
  key    = var.feature_engineer_script_key
  source = var.feature_engineer_script_path
  etag   = filemd5(var.feature_engineer_script_path)
}

resource "aws_glue_job" "feature_engineer" {
  name              = local.feature_job_name
  role_arn          = var.data_engineer_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  max_retries       = 0
  timeout           = 60

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/${var.feature_engineer_script_key}"
  }

  connections = [aws_glue_connection.network.name]

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--job-language"            = "python"
    "--enable-glue-datacatalog" = "true"
    "--enable-metrics"          = "true"
    "--input_path"              = local.processed_output_path
    "--output_path"             = local.features_output_path
    "--feature_group_name"      = var.feature_group_name
    "--region"                  = var.aws_region
    "--TempDir"                 = "s3://${var.bucket_name}/artifacts/glue/temp/"
  }

  depends_on = [
    aws_s3_object.feature_engineer_script,
    aws_glue_job.transform,
  ]
}
