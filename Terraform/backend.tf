# backend.tf

terraform {
  backend "s3" {
    # Replace with the values you created in Step 0
    bucket         = "projectdevops-costbot-tfstate" # The name of the S3 bucket
    key            = "global/aws-costbot/terraform.tfstate" # The path to the state file inside the bucket
    region         = "us-east-1"
    dynamodb_table = "aws-costbot-tf-lock-table"
    encrypt        = true
  }
}