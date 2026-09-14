variable "environment" { type = string; default = "dev" }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "container_image" { type = string; default = "research-platform:latest" }
variable "postgres_host" { type = string }
variable "postgres_db" { type = string }
variable "postgres_user" { type = string }
variable "postgres_password" { type = string; sensitive = true }
variable "redis_host" { type = string }
variable "bedrock_guardrail_id" { type = string; default = "" }
variable "bedrock_guardrail_version" { type = string; default = "DRAFT" }
variable "aws_region" { type = string; default = "us-east-1" }
