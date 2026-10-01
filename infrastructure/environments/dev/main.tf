# ── environments/dev ─────────────────────────────────────────────────────────
# Wire the four modules together here. Each module call passes var.project and
# var.environment down; nothing in modules/ hardcodes a name.
#
module "vpc" {
  source              = "../../modules/vpc"
  project             = var.project
  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  public_subnet_cidr  = var.public_subnet_cidr
  availability_zone   = var.availability_zone
  private_subnet_cidr = var.private_subnet_cidr
}

module "storage" {
  source      = "../../modules/storage"
  project     = var.project
  environment = var.environment
}

module "iam" {
  source      = "../../modules/iam"
  project     = var.project
  environment = var.environment
}

module "sagemaker" {
  source             = "../../modules/sagemaker"
  project            = var.project
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = [module.vpc.private_subnet_id]
  security_group_ids = [module.vpc.security_group_id]
  execution_role_arn = module.iam.ml_engineer_role_arn
  instance_type      = var.sagemaker_instance_type
}

module "glue" {
  source = "../../modules/glue"

  project                = var.project
  environment            = var.environment
  bucket_name            = module.storage.bucket_name
  data_engineer_role_arn = module.iam.data_engineer_role_arn
  private_subnet_id      = module.vpc.private_subnet_id
  security_group_id      = module.vpc.security_group_id
  availability_zone      = var.availability_zone

  transform_script_path = abspath(
    "${path.root}/../../../glue-scripts/transform.py"
  )

  feature_engineer_script_path = abspath(
    "${path.root}/../../../glue-scripts/feature_engineer.py"
  )
  feature_group_name = "${var.project}-${var.environment}-customer-features"
  aws_region         = var.aws_region

  depends_on = [module.feature_store]
}

module "feature_store" {
  source = "../../modules/feature_store"

  feature_group_name     = "${var.project}-${var.environment}-customer-features"
  data_engineer_role_arn = module.iam.data_engineer_role_arn
  offline_store_s3_uri   = "s3://${module.storage.bucket_name}/features/customers/"
}
