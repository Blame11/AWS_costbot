variable "aws_region" {
  description = "The primary AWS region for deploying core resources."
  type        = string
  default     = "us-east-1"
}

variable "notification_email" {
  description = "The email address to receive cost reports."
  type        = string
}

variable "project_name" {
  description = "A unique name for the project to prefix resources."
  type        = string
  default     = "aws-cost-bot"
}

variable "required_tags" {
  description = "A list of tags that must be present on resources."
  type        = list(string)
  default     = ["CostCenter", "Owner", "Project"]
}

variable "idle_cpu_threshold" {
  description = "The CPU utilization percentage below which an EC2 instance is considered idle."
  type        = number
  default     = 5
}