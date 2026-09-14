terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source        = "./modules/vpc"
  environment   = var.environment
  vpc_cidr      = var.vpc_cidr
  single_az_dev = var.single_az_dev
}

module "bedrock" {
  source      = "./modules/bedrock"
  environment = var.environment
}

module "rds" {
  source                = "./modules/rds"
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  ecs_security_group_id = module.ecs.ecs_tasks_security_group_id
  database_name         = var.database_name
  master_username       = var.postgres_user
  master_password       = var.postgres_password
}

module "elasticache" {
  source                = "./modules/elasticache"
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  ecs_security_group_id = module.ecs.ecs_tasks_security_group_id
}

module "ecs" {
  source                   = "./modules/ecs"
  environment              = var.environment
  vpc_id                   = module.vpc.vpc_id
  public_subnet_ids        = module.vpc.public_subnet_ids
  private_subnet_ids       = module.vpc.private_subnet_ids
  container_image          = var.container_image
  postgres_host            = module.rds.endpoint
  postgres_db              = var.database_name
  postgres_user            = var.postgres_user
  postgres_password        = var.postgres_password
  redis_host               = module.elasticache.primary_endpoint_address
  bedrock_guardrail_id     = module.bedrock.guardrail_id
  bedrock_guardrail_version = module.bedrock.guardrail_version
  aws_region               = var.aws_region
}

module "eventbridge" {
  source      = "./modules/eventbridge"
  environment = var.environment
}
