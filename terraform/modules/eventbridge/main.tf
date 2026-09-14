terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_cloudwatch_event_rule" "weekly_redteam" {
  name                = "${var.environment}-weekly-redteam-audit"
  description         = "Trigger weekly automated PyRIT adversarial stress testing"
  schedule_expression = "cron(0 0 ? * SUN *)"
}

resource "aws_cloudwatch_log_group" "redteam_events" {
  name              = "/aws/events/${var.environment}-redteam-audit"
  retention_in_days = 30
}
