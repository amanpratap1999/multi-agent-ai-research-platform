variable "aws_region" {
  type        = string
  description = "AWS Region to deploy resources"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
  default     = "dev"
}

variable "vpc_cidr" {
  type        = string
  description = "Base CIDR block for VPC"
  default     = "10.0.0.0/16"
}

variable "single_az_dev" {
  type        = bool
  description = "Set to true for single-AZ dev profile ($0 idle NAT Gateway fees)"
  default     = true
}

variable "container_image" {
  type        = string
  description = "ECR or Docker container image URI"
  default     = "research-platform:latest"
}

variable "database_name" {
  type    = string
  default = "research_db"
}

variable "postgres_user" {
  type    = string
  default = "postgres"
}

variable "postgres_password" {
  type        = string
  sensitive   = true
  default     = "P@ssw0rdSecurePgVector2026"
}
