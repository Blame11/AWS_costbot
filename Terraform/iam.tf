# iam.tf

resource "aws_iam_role" "lambda_exec_role" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
  tags = {
    Project = var.project_name
  }
}

resource "aws_iam_policy" "lambda_exec_policy" {
  name        = "${var.project_name}-lambda-policy"
  description = "Permissions for the AWS Cost Optimization Bot Lambda"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "AllowEC2Read",
        Effect   = "Allow",
        Action   = [
          "ec2:DescribeRegions",
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeAddresses"
        ],
        Resource = "*" # These actions are required on all resources across regions
      },
      {
        Sid      = "AllowEC2WriteForCleanup",
        Effect   = "Allow",
        Action   = [
          "ec2:StopInstances",
          "ec2:CreateSnapshot",
          "ec2:DeleteVolume",
          "ec2:ReleaseAddress"
        ],
        Resource = "*" # Allow cleanup actions on specific resources, dynamically determined by the Lambda
      },
      {
        Sid      = "AllowCloudWatchRead",
        Effect   = "Allow",
        Action   = "cloudwatch:GetMetricStatistics",
        Resource = "*"
      },
      {
        Sid      = "AllowS3AccessForReports",
        Effect   = "Allow",
        Action   = ["s3:PutObject", "s3:GetObject"],
        Resource = "${aws_s3_bucket.reports_bucket.arn}/*" # Only allow access to objects in our bucket
      },
      {
        Sid      = "AllowSnsPublish",
        Effect   = "Allow",
        Action   = "sns:Publish",
        Resource = aws_sns_topic.cost_report_topic.arn # Only allow publishing to our specific topic
      },
      {
        Sid      = "AllowLogging",
        Effect   = "Allow",
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_exec_policy.arn
}