output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecs_tasks_security_group_id" {
  value = aws_security_group.ecs_tasks.id
}
