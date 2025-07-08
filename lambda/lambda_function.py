import os
import json
import datetime
import logging
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration from Environment Variables ---
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
IDLE_CPU_THRESHOLD = float(os.environ.get('IDLE_CPU_THRESHOLD', 5.0))
REQUIRED_TAGS = os.environ.get('REQUIRED_TAGS', '').split(',')

# --- Boto3 Clients (initialized once) ---
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
ec2_global_client = boto3.client('ec2')

def lambda_handler(event, context):
    """
    Main handler. Routes traffic based on the 'action' in the event payload.
    - 'scan' (default): Finds cost-wasting resources.
    - 'cleanup': Cleans up resources from a specific report file in S3.
    """
    action = event.get('action', 'scan') # Default to 'scan' if no action is specified
    logger.info(f"Executing action: {action}")

    if action == 'scan':
        return run_scan()
    elif action == 'cleanup':
        report_id = event.get('report_id')
        if not report_id:
            return {'statusCode': 400, 'body': json.dumps('Error: report_id is required for cleanup action.')}
        return run_cleanup(report_id)
    else:
        return {'statusCode': 400, 'body': json.dumps(f"Error: Unknown action '{action}'.")}


def run_scan():
    """Scans all regions for findings and generates a report."""
    report = {
        'idle_instances': [],
        'unattached_volumes': [],
        'unassociated_eips': [],
        'untagged_volumes': [],
    }
    
    regions = [r['RegionName'] for r in ec2_global_client.describe_regions()['Regions']]

    for region in regions:
        logger.info(f"Scanning region: {region}")
        ec2_res = boto3.resource('ec2', region_name=region)
        ec2_cli = boto3.client('ec2', region_name=region)
        cw_cli = boto3.client('cloudwatch', region_name=region)

        try:
            # 1. Find idle EC2 instances
            for inst in ec2_res.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
                stats = cw_cli.get_metric_statistics(
                    Namespace='AWS/EC2', MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': inst.id}],
                    StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=14),
                    EndTime=datetime.datetime.utcnow(), Period=86400, Statistics=['Average']
                )
                if stats['Datapoints'] and stats['Datapoints'][0]['Average'] < IDLE_CPU_THRESHOLD:
                    report['idle_instances'].append({'id': inst.id, 'type': inst.instance_type, 'region': region})

            # 2. Find unattached EBS volumes
            for vol in ec2_res.volumes.filter(Filters=[{'Name': 'status', 'Values': ['available']}]):
                cost = vol.size * 0.10  # Simplified monthly cost
                report['unattached_volumes'].append({'id': vol.id, 'size': vol.size, 'region': region, 'cost': cost})
                
            # 3. Find unassociated Elastic IPs
            for addr in ec2_cli.describe_addresses().get('Addresses', []):
                if not addr.get('AssociationId'):
                    report['unassociated_eips'].append({'ip': addr['PublicIp'], 'id': addr.get('AllocationId'), 'region': region})

            # 4. Find volumes missing required tags
            for vol in ec2_res.volumes.all():
                tag_keys = [t['Key'] for t in (vol.tags or [])]
                missing_tags = [rt for rt in REQUIRED_TAGS if rt and rt not in tag_keys]
                if missing_tags:
                    report['untagged_volumes'].append({'id': vol.id, 'region': region, 'missing_tags': missing_tags})

        except ClientError as e:
            logger.error(f"Error scanning region {region}: {e}")
            continue

    # --- Generate, save, and send the report ---
    if not any(report.values()):
        logger.info("No findings found. Exiting.")
        return {'status': 'completed', 'summary': 'No findings.'}
        
    report_id = f"report-{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')}.json"
    
    # Save detailed report to S3
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"reports/{report_id}",
            Body=json.dumps(report, indent=2)
        )
        logger.info(f"Successfully saved report {report_id} to S3 bucket {S3_BUCKET_NAME}.")
    except ClientError as e:
        logger.error(f"Error saving report to S3: {e}")
        raise
    
    # Send summary notification to SNS
    summary_message = generate_summary_message(report, report_id)
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject='[Action Required] Daily AWS Cost Optimization Report',
            Message=summary_message
        )
        logger.info("Successfully sent notification to SNS.")
    except ClientError as e:
        logger.error(f"Error sending SNS notification: {e}")
        raise
        
    return {'status': 'scan_completed', 'report_id': report_id}

def run_cleanup(report_id):
    """
    Reads a report from S3 and performs cleanup actions.
    This function is idempotent.
    """
    logger.info(f"Starting cleanup process for report_id: {report_id}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=f"reports/{report_id}")
        report_data = json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        logger.error(f"Failed to fetch report {report_id} from S3. Error: {e}")
        return {'statusCode': 404, 'body': json.dumps(f"Report {report_id} not found.")}
    
    cleanup_log = []

    # 1. Stop Idle Instances
    for item in report_data.get('idle_instances', []):
        try:
            ec2_cli = boto3.client('ec2', region_name=item['region'])
            ec2_cli.stop_instances(InstanceIds=[item['id']])
            log = f"SUCCESS: Stopped EC2 instance {item['id']} in {item['region']}"
            logger.info(log)
            cleanup_log.append(log)
        except ClientError as e:
            log = f"ERROR: Could not stop instance {item['id']}: {e}"
            logger.error(log)
            cleanup_log.append(log)

    # 2. Snapshot and Delete Unattached Volumes
    for item in report_data.get('unattached_volumes', []):
        try:
            ec2_cli = boto3.client('ec2', region_name=item['region'])
            snapshot = ec2_cli.create_snapshot(
                VolumeId=item['id'],
                Description=f"Pre-deletion snapshot for {item['id']} by Cost Bot."
            )
            logger.info(f"Created snapshot {snapshot['SnapshotId']} for volume {item['id']}")
            ec2_cli.delete_volume(VolumeId=item['id'])
            log = f"SUCCESS: Snapshotted and deleted EBS volume {item['id']} in {item['region']}"
            logger.info(log)
            cleanup_log.append(log)
        except ClientError as e:
            log = f"ERROR: Could not process volume {item['id']}: {e}"
            logger.error(log)
            cleanup_log.append(log)
    
    # 3. Release Unassociated Elastic IPs
    for item in report_data.get('unassociated_eips', []):
        try:
            ec2_cli = boto3.client('ec2', region_name=item['region'])
            ec2_cli.release_address(AllocationId=item['id'])
            log = f"SUCCESS: Released EIP {item['ip']} in {item['region']}"
            logger.info(log)
            cleanup_log.append(log)
        except ClientError as e:
            log = f"ERROR: Could not release EIP {item['ip']}: {e}"
            logger.error(log)
            cleanup_log.append(log)
    
    # No action for untagged volumes, they are for reporting only.
    
    return {'status': 'cleanup_completed', 'log': cleanup_log}


def generate_summary_message(report, report_id):
    """Formats a human-readable summary for SNS notifications."""
    message = f"""
AWS Cost Optimization Bot - Daily Summary

Report ID: {report_id}
(Use this ID to approve cleanup actions in Jenkins)

--------------------------------------------------
SUMMARY OF FINDINGS:
--------------------------------------------------
- Idle EC2 Instances (CPU < {IDLE_CPU_THRESHOLD}% over 14 days): {len(report['idle_instances'])}
- Unattached EBS Volumes: {len(report['unattached_volumes'])}
- Unassociated Elastic IPs: {len(report['unassociated_eips'])}
- Volumes Missing Required Tags: {len(report['untagged_volumes'])}
--------------------------------------------------

DETAILED FINDINGS PREVIEW:
--------------------------------------------------

Idle Instances:
{[i['id'] for i in report['idle_instances'][:5]]}...

Unattached Volumes:
{[v['id'] for v in report['unattached_volumes'][:5]]}...

Unassociated EIPs:
{[e['ip'] for e in report['unassociated_eips'][:5]]}...

Untagged Volumes:
{[v['id'] for v in report['untagged_volumes'][:5]]}...

--------------------------------------------------
To perform cleanup (Stop Instances, Snapshot & Delete Volumes, Release EIPs), please run the 'Cleanup' Jenkins pipeline with the Report ID provided above.
"""
    return message