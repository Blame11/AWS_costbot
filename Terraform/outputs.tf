output "lambda_function_name" {
  value = aws_lambda_function.cost_bot_lambda.function_name
}
output "iam_role_arn" {
  value = aws_iam_role.lambda_exec_role.arn
}
output "s3_reports_bucket_name" {
  value = aws_s3_bucket.reports_bucket.bucket
}
output "sns_topic_arn" {
  value = aws_sns_topic.cost_report_topic.arn
}