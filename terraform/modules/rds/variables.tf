variable "environment" {
  type        = string
  description = "Environment name"
  default     = "dev"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for DB subnet group"
}

variable "ecs_security_group_id" {
  type        = string
  description = "Security group ID of ECS tasks"
}

variable "database_name" {
  type        = string
  default     = "research_db"
}

variable "master_username" {
  type        = string
  default     = "postgres"
}

variable "master_password" {
  type        = string
  sensitive   = true
  default     = "P@ssw0rdSecurePgVector2026"
}
