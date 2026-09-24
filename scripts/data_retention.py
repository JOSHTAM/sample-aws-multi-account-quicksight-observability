"""
Data Retention Lambda Function

Runs daily (scheduled at 02:00 UTC via EventBridge) to enforce data retention
policy by deleting records older than RETENTION_DAYS from the cloudwatch_metrics
and alarm_states tables.

Uses RDS Data API to execute DELETE statements against Aurora PostgreSQL.
"""

import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
AURORA_CLUSTER_ARN = os.environ.get("AURORA_CLUSTER_ARN")
AURORA_SECRET_ARN = os.environ.get("AURORA_SECRET_ARN")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "view360")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "90"))

# AWS clients
rds_client = boto3.client("rds-data")


def lambda_handler(event, context):
    """
    Entry point for the Data Retention Lambda function.

    Deletes records older than RETENTION_DAYS from cloudwatch_metrics
    and alarm_states tables. Logs the count of rows deleted from each table.

    Args:
        event: Lambda event (unused, triggered by EventBridge schedule).
        context: Lambda context object.

    Returns:
        Dict with statusCode and summary of deleted rows.
    """
    start_time = time.time()

    logger.info(
        f"Data retention execution started: "
        f"retention_days={RETENTION_DAYS}, database={DATABASE_NAME}"
    )

    metrics_deleted = 0
    alarms_deleted = 0
    errors = []

    # Delete old records from cloudwatch_metrics
    try:
        metrics_deleted = _delete_old_records(
            table="cloudwatch_metrics",
            retention_days=RETENTION_DAYS,
        )
        logger.info(f"Deleted {metrics_deleted} rows from cloudwatch_metrics")
    except Exception as e:
        error_msg = f"Failed to delete from cloudwatch_metrics: {e}"
        logger.error(error_msg)
        errors.append(error_msg)

    # Delete old records from alarm_states
    try:
        alarms_deleted = _delete_old_records(
            table="alarm_states",
            retention_days=RETENTION_DAYS,
        )
        logger.info(f"Deleted {alarms_deleted} rows from alarm_states")
    except Exception as e:
        error_msg = f"Failed to delete from alarm_states: {e}"
        logger.error(error_msg)
        errors.append(error_msg)

    duration = time.time() - start_time

    logger.info(
        f"Data retention execution completed: "
        f"metrics_deleted={metrics_deleted}, "
        f"alarms_deleted={alarms_deleted}, "
        f"errors={len(errors)}, "
        f"duration={duration:.2f}s"
    )

    return {
        "statusCode": 200 if not errors else 207,
        "body": {
            "metrics_deleted": metrics_deleted,
            "alarms_deleted": alarms_deleted,
            "retention_days": RETENTION_DAYS,
            "errors": errors,
            "duration_seconds": round(duration, 2),
        },
    }


def _delete_old_records(table, retention_days):
    """
    Delete records older than the specified retention period from a table.

    Uses RDS Data API execute_statement with parameterized interval.

    Args:
        table: Table name ('cloudwatch_metrics' or 'alarm_states').
        retention_days: Number of days to retain data.

    Returns:
        Number of rows deleted.

    Raises:
        ClientError: If the RDS Data API call fails.
        Exception: For unexpected errors.
    """
    # RDS Data API does not support parameter substitution inside INTERVAL literals,
    # so we construct the interval as a string directly (safe since retention_days is an int
    # sourced from an environment variable, not user input)
    sql = f"DELETE FROM {table} WHERE collected_at < NOW() - INTERVAL '{retention_days} days'"

    try:
        response = rds_client.execute_statement(
            resourceArn=AURORA_CLUSTER_ARN,
            secretArn=AURORA_SECRET_ARN,
            database=DATABASE_NAME,
            sql=sql,
        )
        rows_affected = response.get("numberOfRecordsUpdated", 0)
        return rows_affected

    except ClientError as e:
        logger.error(
            f"RDS Data API execute_statement failed for {table}: "
            f"{e.response['Error']['Code']} - {e.response['Error']['Message']}"
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting from {table}: {e}")
        raise
