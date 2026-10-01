output "database_name" {
  description = "Glue Catalog database name"
  value       = aws_glue_catalog_database.this.name
}

output "crawler_name" {
  description = "Raw customer crawler name"
  value       = aws_glue_crawler.raw.name
}

output "transform_job_name" {
  description = "Transform Glue job name"
  value       = aws_glue_job.transform.name
}

output "feature_engineer_job_name" {
  description = "Feature engineering Glue job name"
  value       = aws_glue_job.feature_engineer.name
}

output "connection_name" {
  description = "Glue network connection name"
  value       = aws_glue_connection.network.name
}
