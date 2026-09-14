output "alb_dns_name" {
  value       = module.ecs.alb_dns_name
  description = "Public URL endpoint for the Multi-Agent Research Platform"
}

output "rds_cluster_endpoint" {
  value       = module.rds.endpoint
  description = "Aurora Serverless v2 PostgreSQL Endpoint"
}

output "redis_endpoint" {
  value       = module.elasticache.primary_endpoint_address
  description = "ElastiCache Redis Endpoint"
}

output "bedrock_guardrail_id" {
  value       = module.bedrock.guardrail_id
  description = "AWS Bedrock Guardrail ID"
}
