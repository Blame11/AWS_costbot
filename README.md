# AWS Cost Optimization & Cleanup Bot

This project provides a **serverless, automated solution** for identifying and managing wasteful AWS resources to help control cloud costs. The bot scans your AWS account across all regions for common sources of waste, generates daily reports, and provides a safe, approval-based mechanism for cleanup.

---

## Features

- **Multi-Region Scanning:** Automatically scans all available AWS regions.
- **Serverless Architecture:** Built entirely on AWS Lambda, S3, SNS, and EventBridge for low cost and zero maintenance.
- **Waste Detection:** Identifies:
  - **Idle EC2 Instances:** Based on low CPU utilization over a 14-day period.
  - **Unattached EBS Volumes:** "Available" volumes not connected to any EC2 instance.
  - **Unassociated Elastic IPs (EIPs):** EIPs that are allocated but not attached to an instance or network interface.
  - **Resources Missing Tags:** Reports resources that are missing essential governance tags (e.g., `CostCenter`, `Project`).
- **Daily Reporting:** Sends a summary of findings via email (SNS) every day.
- **Safe, Idempotent Cleanup:** A Jenkins pipeline with manual approval allows operators to:
  - Stop idle EC2 instances (instead of terminating).
  - Snapshot unattached EBS volumes before deleting them.
  - Release unassociated EIPs.
- **Infrastructure as Code (IaC):** All AWS infrastructure is managed with Terraform, enabling easy, repeatable deployments.
- **CI/CD Integration:** Jenkins pipelines manage infrastructure deployment and on-demand cleanup actions.
- **Stateful Operations:** Cleanup actions are based on specific, versioned reports stored in S3, preventing accidental deletion of newly created resources.

---

## Architecture

![Untitled diagram _ Mermaid Chart-2025-07-08-094017](https://github.com/user-attachments/assets/6a2bbebf-0cf5-4b6f-aab4-6b12ba43e659)


**Scheduled Scan (Daily):**
- An Amazon EventBridge rule triggers the Lambda function on a daily cron schedule.
- The Lambda function (`aws-cost-bot`) scans all AWS regions for wasteful resources using Boto3.
- A detailed JSON report is generated, assigned a unique Report ID, and saved to a private S3 bucket.
- A human-readable summary, including the Report ID, is published to an SNS topic, which sends an email to subscribed stakeholders.

**Manual Cleanup (On-Demand):**
- A DevOps engineer receives the email and decides to take action.
- They trigger a parameterized Jenkins pipeline, providing the Report ID from the email.
- The pipeline has a manual "input" step, requiring explicit approval before proceeding.
- Upon approval, the pipeline invokes the same Lambda function but with a cleanup action payload, including the Report ID.
- The Lambda function reads the specified report from S3 and performs the cleanup actions (stop, snapshot, delete, release) on the resources listed in that specific file.

---

## Prerequisites

- An AWS Account with permissions to create IAM, S3, Lambda, SNS, EventBridge, and DynamoDB resources.
- AWS CLI configured on your local machine.
- Terraform (version 1.0.0+) installed.
- A Git repository for storing the project code.
- A Jenkins instance with:
  - AWS credentials (with permissions to deploy and manage resources).
  - Pipeline plugin, AWS Steps plugin.

---

## Deployment Instructions

### 1. Set Up the Terraform Backend

This is a one-time setup to create a secure, remote backend for Terraform state management.

**Choose Unique Names:** Pick a globally unique name for your S3 bucket.

**Execute Setup Script:** Run the following commands in your terminal, replacing the placeholder values.

```bash
# IMPORTANT: Replace with your own unique values
export TF_STATE_BUCKET="your-unique-name-costbot-tfstate"
export TF_LOCK_TABLE="aws-costbot-tf-lock-table"
export AWS_REGION="us-east-1"

# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket ${TF_STATE_BUCKET} --region ${AWS_REGION} \
  --create-bucket-configuration LocationConstraint=${AWS_REGION}
aws s3api put-bucket-versioning --bucket ${TF_STATE_BUCKET} --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket ${TF_STATE_BUCKET} --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'
aws s3api put-public-access-block --bucket ${TF_STATE_BUCKET} --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name ${TF_LOCK_TABLE} \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 2. Configure the Project

**Clone the Repository:**

```bash
git clone https://github.com/your-org/aws-costbot.git
cd aws-costbot
```

**Configure Terraform Backend File:**

Edit [`Terraform/backend.tf`](Terraform/backend.tf) and update the `bucket` and `dynamodb_table` values to match what you created in Step 1.

**Review Terraform Variables:**

Edit [`Terraform/variables.tf`](Terraform/variables.tf). Review the default values for `project_name`, `required_tags`, and `idle_cpu_threshold` and adjust them to your organization's standards.

**Configure Jenkins Pipelines:**

- Update the deployment [`jenkins/Jenkinsfile`](jenkins/Jenkinsfile) and cleanup [`jenkins/cleanup/jenkinsfile`](jenkins/cleanup/jenkinsfile).
- Set your Jenkins Credentials IDs and your repository URL.

### 3. Run the Deployment Pipeline

- Push your configured code to your repository.
- Trigger the main deployment pipeline in Jenkins.

The pipeline will:
- Run `terraform init` to connect to your S3 backend.
- Run `terraform plan` to show you the planned changes.
- Wait for manual approval to apply the infrastructure.
- Once approved, it will run `terraform apply`.
- Finally, it will package the Python code and deploy it to the newly created Lambda function.

After the pipeline succeeds, check your email for the SNS topic subscription confirmation and click the link to confirm.

---

## Usage

### Receiving Reports

You will automatically receive an email report every day at the time configured in [`Terraform/eventbridge.tf`](Terraform/eventbridge.tf) (default is 2:00 AM UTC).  
The email contains a summary of findings and a Report ID (e.g., `report-2023-10-28-14-30-00.json`).

### Performing Cleanup

1. Log in to Jenkins and find the Cost Bot Cleanup pipeline.
2. Click **"Build with Parameters"**.
3. Paste the Report ID from the email into the `REPORT_ID` parameter field.
4. Start the build.
5. The pipeline will pause and ask for Manual Approval. Review the Report ID one last time.
6. Click **"Proceed"** to approve.
7. The pipeline will invoke the Lambda function, which will perform the cleanup actions and log its progress.  
   You can check the Jenkins build logs or the Lambda's CloudWatch logs for details.

---

## Future Enhancements & Customization

- **Add More Services:** Extend the Lambda function to scan for other wasteful resources like:
  - Unused RDS Snapshots or Instances
  - Old, unreferenced AMIs
  - Underutilized NAT Gateways
- **Integrate with AWS Cost Explorer:** Pull actual cost data instead of using estimates.
- **Alternative Notifications:** Send reports to Slack, Microsoft Teams, or other messaging platforms.
- **Configuration as Code:** Move thresholds and settings from environment variables to AWS SSM Parameter Store or AWS AppConfig for dynamic updates without redeploying code.
- **Automated Cleanup:** For high-confidence findings (e.g., unattached volumes older than 30 days), you could create a fully automated cleanup flow without manual approval. **Use with extreme caution.**

---

## Repository Structure

```
README.md
backendResorces/
    terraformBackend
jenkins/
    Jenkinsfile
    cleanup/
        jenkinsfile
lambda/
    lambda_function.py
    requirements.txt
Terraform/
    backend.tf
    eventbridge.tf
    iam.tf
    lambda.tf
    outputs.tf
    s3.tf
    sns.tf
    variables.tf
```

---

