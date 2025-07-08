# sns.tf
resource "aws_sns_topic" "cost_report_topic" {
  name = "${var.project_name}-reports"
}

resource "aws_sns_topic_subscription" "email_subscription" {
  topic_arn = aws_sns_topic.cost_report_topic.arn
  protocol  = "email"
  endpoint  = var.notification_email
}
