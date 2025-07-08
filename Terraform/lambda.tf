# lambda.tf

# This data source zips our Python code for deployment
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/"
  output_path = "${path.module}/../lambda.zip"
}

resource "aws_lambda_function" "cost_bot_lambda" {
  function_name = var.project_name
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_exec_role.arn
  timeout       = 300 # 5 minutes, as scanning all regions can be slow

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET_NAME     = aws_s3_bucket.reports_bucket.bucket
      SNS_TOPIC_ARN      = aws_sns_topic.cost_report_topic.arn
      IDLE_CPU_THRESHOLD = var.idle_cpu_threshold
      REQUIRED_TAGS      = join(",", var.required_tags) # Pass list as comma-separated string
    }
  }

  tags = {
    Project = var.project_name
  }
}