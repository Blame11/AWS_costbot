# eventbridge.tf
resource "aws_cloudwatch_event_rule" "daily_scan_rule" {
  name                = "${var.project_name}-daily-scan"
  description         = "Triggers the cost bot to scan for wasteful resources."
  schedule_expression = "cron(0 2 * * ? *)" # 2 AM UTC daily
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_scan_rule.name
  arn       = aws_lambda_function.cost_bot_lambda.arn
  # We can pass a specific payload for the scan event if needed
  # input = jsonencode({"action": "scan"})
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeToInvokeLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_bot_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_scan_rule.arn
}
