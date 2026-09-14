variable "environment" {
  type        = string
  description = "Deployment environment name"
  default     = "dev"
}

variable "vpc_cidr" {
  type        = string
  description = "Base CIDR block for VPC"
  default     = "10.0.0.0/16"
}

variable "single_az_dev" {
  type        = bool
  description = "Whether to use single-AZ to eliminate NAT Gateway costs in development"
  default     = true
}
