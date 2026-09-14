output "endpoint" {
  value       = aws_rds_cluster.aurora.endpoint
  description = "The cluster endpoint for Aurora PostgreSQL"
}

output "reader_endpoint" {
  value       = aws_rds_cluster.aurora.reader_endpoint
  description = "The reader endpoint for Aurora PostgreSQL"
}

output "port" {
  value       = aws_rds_cluster.aurora.port
  description = "The port for Aurora PostgreSQL"
}

output "database_name" {
  value       = aws_rds_cluster.aurora.database_name
}
