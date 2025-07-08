# s3.tf
resource "aws_s3_bucket" "reports_bucket" {
  bucket = "${var.project_name}-reports-${random_id.bucket_id.hex}"
  # Forcing TLS is a security best practice
  force_destroy = false # Set to true only for dev environments
}

resource "random_id" "bucket_id" {
  byte_length = 8
}

resource "aws_s3_bucket_public_access_block" "reports_bucket_pab" {
  bucket                  = aws_s3_bucket.reports_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
