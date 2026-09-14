output "guardrail_id" {
  value = aws_bedrock_guardrail.main.guardrail_id
}

output "guardrail_arn" {
  value = aws_bedrock_guardrail.main.guardrail_arn
}

output "guardrail_version" {
  value = aws_bedrock_guardrail_version.main.version
}
