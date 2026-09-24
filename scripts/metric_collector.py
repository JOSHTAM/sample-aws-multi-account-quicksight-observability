"""
Metric Collector Lambda Function

Collects CloudWatch metrics from all monitored member accounts every 5 minutes
and writes them to Aurora PostgreSQL via the RDS Data API.

Execution flow:
1. Load configuration (metric_definitions.json, exclude.json) from S3
2. For each configured namespace:
   - Determine region (us-east-1 for CloudFront/ACM, ap-southeast-1 for others)
   - Discover resources via list_metrics (IncludeLinkedAccounts=True)
   - Apply exclusion filters
   - Build GetMetricData queries in batches of 500
   - Execute batched GetMetricData calls (300-second period)
   - Write results to Aurora via RDS Data API
3. Collect alarm states
4. Log execution summary
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
AURORA_CLUSTER_ARN = os.environ.get("AURORA_CLUSTER_ARN")
AURORA_SECRET_ARN = os.environ.get("AURORA_SECRET_ARN")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "view360")
CONFIG_BUCKET = os.environ.get("CONFIG_BUCKET")
METRIC_DEFINITIONS_KEY = os.environ.get("METRIC_DEFINITIONS_KEY", "config/metric_definitions.json")
EXCLUDE_RULES_KEY = os.environ.get("EXCLUDE_RULES_KEY", "config/exclude.json")

# AWS clients (initialized per region as needed)
s3_client = boto3.client("s3")
rds_client = boto3.client("rds-data")


def lambda_handler(event, context):
    """
    Entry point for the Metric Collector Lambda function.
    Orchestrates: discovery → filtering → collection → write for each namespace.
    """
    start_time = time.time()
    total_metrics_collected = 0
    total_errors = 0

    logger.info("Metric Collector execution started")

    # Step 1: Load configuration from S3
    try:
        metric_definitions = load_config_from_s3(CONFIG_BUCKET, METRIC_DEFINITIONS_KEY)
        exclusion_rules = load_config_from_s3(CONFIG_BUCKET, EXCLUDE_RULES_KEY)
    except Exception as e:
        logger.error(f"Failed to load configuration from S3: {e}")
        raise

    accounts = metric_definitions.get("accounts", [])
    default_region = metric_definitions.get("default_region", "ap-southeast-1")
    region_overrides = metric_definitions.get("region_overrides", {})
    metrics_config = metric_definitions.get("metrics", [])

    # Group metrics by namespace for sequential processing
    namespaces = {}
    for metric in metrics_config:
        ns = metric["namespace"]
        if ns not in namespaces:
            namespaces[ns] = []
        namespaces[ns].append(metric)

    # Step 2: Process each namespace sequentially
    for namespace, namespace_metrics in namespaces.items():
        # Check remaining Lambda execution time; break early if < 30s remain
        remaining_ms = context.get_remaining_time_in_millis()
        if remaining_ms < 30000:
            logger.warning(
                f"Less than 30s remaining (remaining_ms={remaining_ms}), "
                f"stopping namespace processing to allow cleanup. "
                f"Skipped namespaces: {list(namespaces.keys())[list(namespaces.keys()).index(namespace):]}"
            )
            break

        try:
            # Determine region for this namespace
            region = region_overrides.get(namespace, default_region)

            # Create CloudWatch client for the appropriate region
            cw_client = boto3.client("cloudwatch", region_name=region)

            # Discover resources for this namespace across all accounts
            discovered = discover_resources(cw_client, namespace, accounts)

            # Apply exclusion filters
            filtered = [
                m for m in discovered if not should_exclude(m, exclusion_rules)
            ]

            if not filtered:
                logger.info(f"No metrics remaining after filtering for {namespace}")
                continue

            # Extract resource IDs for each discovered metric
            for metric in filtered:
                metric["resource_id"] = extract_resource_id(
                    metric.get("dimensions", []), namespace
                )

            # Enrich with statistic and category from config
            enriched = enrich_metrics(filtered, namespace_metrics)

            # Build GetMetricData queries in batches of 500
            query_batches = build_metric_data_queries(enriched)

            # Calculate time window (aligned to 5-minute boundaries)
            now = datetime.now(timezone.utc)
            end_time = now.replace(second=0, microsecond=0)
            end_time = end_time.replace(minute=(end_time.minute // 5) * 5)
            period_start = end_time - timedelta(minutes=5)

            # Execute batched GetMetricData calls
            results = collect_metrics(cw_client, query_batches, enriched, period_start, end_time)

            # Write results to Aurora
            if results:
                write_metrics_batch(
                    rds_client, results, AURORA_CLUSTER_ARN, AURORA_SECRET_ARN, DATABASE_NAME
                )
                total_metrics_collected += len(results)

            logger.info(
                f"Namespace {namespace}: collected {len(results)} data points "
                f"from {len(filtered)} resources in {region}"
            )

        except ClientError as e:
            total_errors += 1
            logger.error(
                f"Failed processing namespace={namespace}, "
                f"accounts={[str(a) for a in accounts]}, "
                f"metrics={[m['metric_name'] for m in namespace_metrics]}, "
                f"error={e.response['Error']['Code']}: "
                f"{e.response['Error']['Message']}"
            )
            continue
        except Exception as e:
            total_errors += 1
            logger.error(
                f"Unexpected error processing namespace={namespace}, "
                f"accounts={[str(a) for a in accounts]}, "
                f"metrics={[m['metric_name'] for m in namespace_metrics]}: {e}"
            )
            continue

    # Step 3: Collect alarm states
    try:
        alarm_records = collect_alarm_states(cw_client, accounts)
        if alarm_records:
            write_alarm_states(
                rds_client, alarm_records, AURORA_CLUSTER_ARN, AURORA_SECRET_ARN, DATABASE_NAME
            )
            logger.info(f"Collected {len(alarm_records)} alarm state records")
    except Exception as e:
        total_errors += 1
        logger.error(f"Failed collecting alarm states: {e}")

    # Step 4: Log execution summary
    duration = time.time() - start_time
    logger.info(
        f"Metric Collector execution completed: "
        f"total_metrics={total_metrics_collected}, "
        f"errors={total_errors}, "
        f"duration={duration:.2f}s"
    )

    return {
        "statusCode": 200,
        "body": {
            "metrics_collected": total_metrics_collected,
            "errors": total_errors,
            "duration_seconds": round(duration, 2),
        },
    }


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------


def load_config_from_s3(bucket, key):
    """Load and parse a JSON configuration file from S3."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


# ---------------------------------------------------------------------------
# Helper: Enrich discovered metrics with statistic and category
# ---------------------------------------------------------------------------


def enrich_metrics(discovered, namespace_metrics):
    """
    Combine discovered metric/dimension pairs with the configured statistics
    and dashboard categories from metric_definitions.json.
    """
    enriched = []
    for discovered_metric in discovered:
        metric_name = discovered_metric.get("metric_name")
        for config in namespace_metrics:
            if config["metric_name"] == metric_name:
                enriched.append(
                    {
                        **discovered_metric,
                        "statistic": config["statistic"],
                        "category": config.get("category", ""),
                    }
                )
    return enriched


# ---------------------------------------------------------------------------
# Stub functions (to be implemented in tasks 3.2 - 3.10)
# ---------------------------------------------------------------------------


def discover_resources(cw_client, namespace, accounts):
    """
    Discover active resources for a namespace using CloudWatch list_metrics.

    Uses IncludeLinkedAccounts=True for cross-account discovery.
    Returns a list of dicts with: namespace, metric_name, dimensions, account_id.
    """
    discovered = []

    for account in accounts:
        try:
            paginator = cw_client.get_paginator("list_metrics")
            page_iterator = paginator.paginate(
                Namespace=namespace,
                OwningAccount=str(account),
                IncludeLinkedAccounts=True,
            )

            for page in page_iterator:
                for metric in page.get("Metrics", []):
                    dimensions = [
                        {"Name": dim["Name"], "Value": dim["Value"]}
                        for dim in metric.get("Dimensions", [])
                    ]
                    discovered.append(
                        {
                            "namespace": metric["Namespace"],
                            "metric_name": metric["MetricName"],
                            "dimensions": dimensions,
                            "account_id": str(account),
                        }
                    )

        except ClientError as e:
            logger.warning(
                f"Failed to discover resources for account={account}, "
                f"namespace={namespace}: {e.response['Error']['Code']} - "
                f"{e.response['Error']['Message']}"
            )
            continue
        except Exception as e:
            logger.warning(
                f"Unexpected error discovering resources for account={account}, "
                f"namespace={namespace}: {e}"
            )
            continue

    logger.info(
        f"Discovered {len(discovered)} metric/dimension combinations "
        f"for namespace={namespace}"
    )
    return discovered


def should_exclude(metric, exclusion_rules):
    """
    Check if a discovered metric should be excluded based on exclusion rules.

    Matches the L2 DashboardCreatorFunction exclusion filter logic.
    Rules support:
      - Namespace regex matching
      - Metric name regex matching
      - Dimension key/value regex matching (single pattern string or list of patterns)
      - EmptyDimensions: true (excludes metrics with no dimensions)

    Args:
        metric: Dict with keys: namespace, metric_name, dimensions
                (dimensions is a list of {"Name": ..., "Value": ...} dicts)
        exclusion_rules: List of rule dicts from exclude.json

    Returns:
        True if the metric should be excluded, False otherwise.
    """
    for rule in exclusion_rules:
        # Check namespace match
        if not re.match(rule["namespace"], metric["namespace"]):
            continue
        # Check metric name match
        if not re.match(rule["metrics"], metric["metric_name"]):
            continue

        # Check EmptyDimensions rule
        if rule.get("EmptyDimensions"):
            if len(metric.get("dimensions", [])) == 0:
                return True

        # Check dimension-specific rules
        for dim in metric.get("dimensions", []):
            if dim["Name"] in rule:
                patterns = rule[dim["Name"]]
                # Normalize to list if a single string pattern
                if isinstance(patterns, str):
                    patterns = [patterns]
                for pattern in patterns:
                    if re.match(pattern, dim["Value"]):
                        return True

    return False


def extract_resource_id(dimensions, namespace):
    """
    Extract the primary resource identifier from metric dimensions.

    Maps namespaces to their primary dimension (e.g., EC2→InstanceId,
    Lambda→FunctionName, RDS→DBInstanceIdentifier).

    Args:
        dimensions: List of {"Name": "...", "Value": "..."} dicts.
        namespace: CloudWatch namespace string (e.g., "AWS/EC2").

    Returns:
        The value of the primary dimension for the namespace,
        or the first dimension's value if no mapping matches,
        or empty string if no dimensions.
    """
    if not dimensions:
        return ""

    # Namespace to primary dimension mapping
    namespace_primary_dimension = {
        "AWS/EC2": "InstanceId",
        "AWS/RDS": "DBInstanceIdentifier",
        "AWS/Lambda": "FunctionName",
        "AWS/ApplicationELB": "LoadBalancer",
        "AWS/ApiGateway": "ApiName",
        "AWS/ECS": "ClusterName",
        "ECS/ContainerInsights": "ClusterName",
        "EKS/ContainerInsights": "ClusterName",
        "AWS/CloudFront": "DistributionId",
        "AWS/S3": "BucketName",
        "AWS/DynamoDB": "TableName",
        "AWS/SQS": "QueueName",
        "CWAgent": "InstanceId",
        "AWS/Logs": "LogGroupName",
        "AWS/Backup": "ResourceType",
        "AWS/CertificateManager": "CertificateArn",
        "AWS/Route53": "HealthCheckId",
    }

    primary_dim_name = namespace_primary_dimension.get(namespace)

    if primary_dim_name:
        for dim in dimensions:
            if dim["Name"] == primary_dim_name:
                return dim["Value"]

    # Fallback: return the first dimension's value
    return dimensions[0]["Value"]


def build_metric_data_queries(enriched_metrics, period=300):
    """
    Build MetricDataQueries in batches of 500 (AWS API limit).

    Each query maps one metric + one resource + one statistic with a unique Id.
    The Id uses the format 'm{index}' which satisfies the CloudWatch API regex
    requirement of [a-z][a-zA-Z0-9_]* (no special characters).

    Args:
        enriched_metrics: List of dicts with keys: namespace, metric_name,
            dimensions (list of {Name, Value}), statistic, category,
            resource_id, account_id.
        period: Query period in seconds (default 300 = 5 minutes).

    Returns:
        A list of batches, where each batch is a list of up to 500 query dicts
        suitable for passing to CloudWatch GetMetricData.
    """
    queries = []
    for i, metric in enumerate(enriched_metrics):
        query = {
            "Id": f"m{i}",
            "MetricStat": {
                "Metric": {
                    "Namespace": metric["namespace"],
                    "MetricName": metric["metric_name"],
                    "Dimensions": metric["dimensions"],
                },
                "Period": period,
                "Stat": metric["statistic"],
            },
            "ReturnData": True,
        }
        # Include AccountId for cross-account metric retrieval
        if metric.get("account_id"):
            query["AccountId"] = metric["account_id"]
        queries.append(query)

    # Split into batches of 500 (AWS GetMetricData API limit)
    return [queries[i : i + 500] for i in range(0, len(queries), 500)]


def collect_metrics(cw_client, query_batches, enriched_metrics, start_time, end_time):
    """
    Execute batched GetMetricData calls and return collected data points.

    Aligns start_time/end_time to 5-minute interval boundaries, handles
    pagination if MetricDataResults are truncated, and maps results back
    to enriched metric metadata using query Id format 'm{index}'.

    Args:
        cw_client: boto3 CloudWatch client configured for the correct region.
        query_batches: List of batches from build_metric_data_queries (each batch
            is a list of up to 500 MetricDataQuery dicts).
        enriched_metrics: List of enriched metric dicts (same order used to
            build query_batches) with keys: namespace, metric_name, dimensions,
            statistic, category, resource_id, account_id.
        start_time: datetime object for the query start (will be aligned to
            5-minute boundary).
        end_time: datetime object for the query end (will be aligned to
            5-minute boundary).

    Returns:
        A list of result dicts ready for Aurora insertion, each containing:
        collected_at, namespace, metric_name, dimensions, resource_id,
        statistic, value, account_id, region, unit, category.
    """
    # Align start_time and end_time to 5-minute interval boundaries
    aligned_start = start_time.replace(second=0, microsecond=0)
    aligned_start = aligned_start.replace(minute=(aligned_start.minute // 5) * 5)
    aligned_end = end_time.replace(second=0, microsecond=0)
    aligned_end = aligned_end.replace(minute=(aligned_end.minute // 5) * 5)

    results = []

    for batch in query_batches:
        # Execute GetMetricData with pagination support
        next_token = None
        while True:
            try:
                params = {
                    "MetricDataQueries": batch,
                    "StartTime": aligned_start,
                    "EndTime": aligned_end,
                }
                if next_token:
                    params["NextToken"] = next_token

                response = cw_client.get_metric_data(**params)

            except ClientError as e:
                logger.error(
                    f"GetMetricData API error: {e.response['Error']['Code']} - "
                    f"{e.response['Error']['Message']}"
                )
                break
            except Exception as e:
                logger.error(f"Unexpected error calling GetMetricData: {e}")
                break

            # Process each MetricDataResult in the response
            for metric_result in response.get("MetricDataResults", []):
                query_id = metric_result["Id"]
                # Extract the index from the query Id format 'm{index}'
                try:
                    metric_index = int(query_id[1:])
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse metric index from Id: {query_id}")
                    continue

                # Look up the enriched metric metadata
                if metric_index >= len(enriched_metrics):
                    logger.warning(
                        f"Metric index {metric_index} out of range "
                        f"(enriched_metrics has {len(enriched_metrics)} entries)"
                    )
                    continue

                enriched = enriched_metrics[metric_index]

                # Each result may have multiple timestamps/values
                timestamps = metric_result.get("Timestamps", [])
                values = metric_result.get("Values", [])

                for ts, val in zip(timestamps, values):
                    results.append(
                        {
                            "collected_at": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                            "namespace": enriched["namespace"],
                            "metric_name": enriched["metric_name"],
                            "dimensions": json.dumps(enriched["dimensions"]),
                            "resource_id": enriched.get("resource_id", ""),
                            "statistic": enriched["statistic"],
                            "value": val,
                            "account_id": enriched.get("account_id", ""),
                            "region": cw_client.meta.region_name,
                            "unit": metric_result.get("Label", ""),
                            "category": enriched.get("category", ""),
                        }
                    )

            # Check if there are more pages of results
            next_token = response.get("NextToken")
            if not next_token:
                break

    logger.info(f"Collected {len(results)} data points from {len(query_batches)} batches")
    return results


def write_metrics_batch(rds_client, metrics, cluster_arn, secret_arn, database):
    """
    Write collected metrics to Aurora PostgreSQL using RDS Data API.

    Uses batch_execute_statement with INSERT ON CONFLICT for idempotent upserts.
    Splits into sub-batches of 1000 (RDS Data API limit per call).

    Args:
        rds_client: boto3 RDS Data API client.
        metrics: List of metric dicts with keys: collected_at, account_id, region,
            namespace, metric_name, dimensions (JSON string), resource_id,
            statistic, value, unit, category.
        cluster_arn: Aurora cluster ARN.
        secret_arn: Secrets Manager ARN for DB credentials.
        database: Database name.
    """
    if not metrics:
        return

    sql = """
        INSERT INTO cloudwatch_metrics
            (collected_at, account_id, region, namespace, metric_name,
             dimensions, resource_id, statistic, value, unit, dashboard_category)
        VALUES
            (CAST(:collected_at AS TIMESTAMP), :account_id, :region, :namespace, :metric_name,
             CAST(:dimensions AS JSONB), :resource_id, :statistic, :value, :unit, :category)
        ON CONFLICT (collected_at, account_id, namespace, metric_name, resource_id, statistic)
        DO UPDATE SET value = EXCLUDED.value
    """

    # Build parameter sets for all metrics
    parameter_sets = [_build_metric_params(m) for m in metrics]

    # RDS Data API batch_execute_statement limit is 1000 parameter sets per call
    batch_size = 1000
    total_written = 0

    for i in range(0, len(parameter_sets), batch_size):
        sub_batch = parameter_sets[i : i + batch_size]
        try:
            rds_client.batch_execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=database,
                sql=sql,
                parameterSets=sub_batch,
            )
            total_written += len(sub_batch)
        except ClientError as e:
            logger.error(
                f"RDS Data API batch_execute_statement failed: "
                f"{e.response['Error']['Code']} - {e.response['Error']['Message']} "
                f"(batch offset={i}, size={len(sub_batch)})"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error writing metrics batch (offset={i}, "
                f"size={len(sub_batch)}): {e}"
            )

    logger.info(f"Wrote {total_written}/{len(metrics)} metric records to Aurora")


def _build_metric_params(metric):
    """
    Convert a metric dict to an RDS Data API parameter set.

    Args:
        metric: Dict with keys: collected_at, account_id, region, namespace,
            metric_name, dimensions, resource_id, statistic, value, unit, category.

    Returns:
        List of parameter dicts for batch_execute_statement.
    """
    return [
        {"name": "collected_at", "value": {"stringValue": str(metric.get("collected_at", ""))}},
        {"name": "account_id", "value": {"stringValue": str(metric.get("account_id", ""))}},
        {"name": "region", "value": {"stringValue": str(metric.get("region", "ap-southeast-1"))}},
        {"name": "namespace", "value": {"stringValue": str(metric.get("namespace", ""))}},
        {"name": "metric_name", "value": {"stringValue": str(metric.get("metric_name", ""))}},
        {"name": "dimensions", "value": {"stringValue": str(metric.get("dimensions", "{}"))}},
        {"name": "resource_id", "value": {"stringValue": str(metric.get("resource_id", ""))}},
        {"name": "statistic", "value": {"stringValue": str(metric.get("statistic", ""))}},
        {"name": "value", "value": {"doubleValue": float(metric.get("value", 0))}},
        {"name": "unit", "value": {"stringValue": str(metric.get("unit", ""))}},
        {"name": "category", "value": {"stringValue": str(metric.get("category", ""))}},
    ]


def collect_alarm_states(cw_client, accounts):
    """
    Collect current alarm states from CloudWatch using describe_alarms.

    Queries all MetricAlarms via the default region client (ap-southeast-1)
    and filters to alarms whose namespace and metric name match the L2
    dashboard metrics defined in metric_definitions.json.

    Args:
        cw_client: boto3 CloudWatch client (kept for backward compat, but
            a default-region client is created internally).
        accounts: List of account ID strings to associate with alarms.

    Returns:
        A list of alarm record dicts with keys: collected_at, account_id,
        alarm_name, namespace, metric_name, dimensions (JSON string),
        resource_id, state, state_reason, state_updated_at.
    """
    # Build a set of (namespace, metric_name) tuples for L2 dashboard filtering
    l2_metrics = _get_l2_dashboard_metrics()

    # Create default region client for alarm queries (cross-account)
    default_cw = boto3.client("cloudwatch", region_name="ap-southeast-1")

    collected_at = datetime.now(timezone.utc).isoformat()
    alarm_records = []

    # Convert accounts list to a set of strings for membership checks
    account_set = set(str(a) for a in accounts)

    try:
        next_token = None
        while True:
            params = {
                "AlarmTypes": ["MetricAlarm"],
                "MaxRecords": 100,
            }
            if next_token:
                params["NextToken"] = next_token

            response = default_cw.describe_alarms(**params)

            for alarm in response.get("MetricAlarms", []):
                namespace = alarm.get("Namespace", "")
                metric_name = alarm.get("MetricName", "")

                # Filter: only include alarms for L2 dashboard metrics
                if (namespace, metric_name) not in l2_metrics:
                    continue

                # Extract dimensions as a list of {Name, Value} dicts
                dimensions = [
                    {"Name": dim["Name"], "Value": dim["Value"]}
                    for dim in alarm.get("Dimensions", [])
                ]

                # Determine account_id from alarm metadata
                # Cross-account alarms may have an OwningAccount field
                # (available with cross-account observability enabled)
                account_id = alarm.get("OwningAccount", "")
                if not account_id:
                    # Fallback: extract from AlarmArn if available
                    alarm_arn = alarm.get("AlarmArn", "")
                    if alarm_arn:
                        # ARN format: arn:aws:cloudwatch:region:account-id:alarm:name
                        arn_parts = alarm_arn.split(":")
                        if len(arn_parts) >= 5:
                            account_id = arn_parts[4]

                # If we have a known accounts list, only include alarms from those accounts
                if account_set and account_id and account_id not in account_set:
                    continue

                # Extract resource_id from dimensions using namespace mapping
                resource_id = extract_resource_id(dimensions, namespace)

                # Get state_updated_at as ISO string
                state_updated_at = alarm.get("StateUpdatedTimestamp")
                if state_updated_at and hasattr(state_updated_at, "isoformat"):
                    state_updated_at = state_updated_at.isoformat()
                else:
                    state_updated_at = str(state_updated_at) if state_updated_at else ""

                alarm_records.append(
                    {
                        "collected_at": collected_at,
                        "account_id": account_id,
                        "alarm_name": alarm.get("AlarmName", ""),
                        "namespace": namespace,
                        "metric_name": metric_name,
                        "dimensions": json.dumps(dimensions),
                        "resource_id": resource_id,
                        "state": alarm.get("StateValue", ""),
                        "state_reason": alarm.get("StateReason", ""),
                        "state_updated_at": state_updated_at,
                    }
                )

            # Handle pagination
            next_token = response.get("NextToken")
            if not next_token:
                break

    except ClientError as e:
        logger.error(
            f"describe_alarms API error: {e.response['Error']['Code']} - "
            f"{e.response['Error']['Message']}"
        )
    except Exception as e:
        logger.error(f"Unexpected error collecting alarm states: {e}")

    logger.info(f"Collected {len(alarm_records)} alarm state records (filtered to L2 metrics)")
    return alarm_records


def _get_l2_dashboard_metrics():
    """
    Return a set of (namespace, metric_name) tuples representing
    the L2 dashboard metrics. Used for filtering alarms to only those
    associated with monitored metrics.

    Loads from metric_definitions.json via S3 if CONFIG_BUCKET is set,
    otherwise falls back to a hardcoded set derived from the design document.
    """
    # Try loading from S3 config if available (runtime scenario)
    if CONFIG_BUCKET:
        try:
            config = load_config_from_s3(CONFIG_BUCKET, METRIC_DEFINITIONS_KEY)
            return {
                (m["namespace"], m["metric_name"])
                for m in config.get("metrics", [])
            }
        except Exception as e:
            logger.warning(f"Could not load metric_definitions from S3 for alarm filtering: {e}")

    # Fallback: hardcoded set of L2 dashboard namespaces/metrics
    return {
        ("AWS/EC2", "StatusCheckFailed"),
        ("AWS/EC2", "StatusCheckFailed_AttachedEBS"),
        ("AWS/EC2", "CPUUtilization"),
        ("AWS/EC2", "NetworkIn"),
        ("AWS/EC2", "NetworkOut"),
        ("AWS/RDS", "EngineUptime"),
        ("AWS/RDS", "CPUUtilization"),
        ("AWS/RDS", "FreeableMemory"),
        ("AWS/RDS", "FreeStorageSpace"),
        ("AWS/RDS", "DiskQueueDepth"),
        ("AWS/RDS", "DatabaseConnections"),
        ("AWS/RDS", "ReadLatency"),
        ("AWS/RDS", "WriteLatency"),
        ("AWS/RDS", "DatabaseConnectionErrors"),
        ("AWS/RDS", "ReadIOPS"),
        ("AWS/RDS", "WriteIOPS"),
        ("AWS/RDS", "Deadlocks"),
        ("AWS/RDS", "SuccessfulTransactions"),
        ("AWS/RDS", "AbortedTransactions"),
        ("AWS/Lambda", "ConcurrentExecutions"),
        ("AWS/Lambda", "Duration"),
        ("AWS/Lambda", "PostRuntimeExtensionsDuration"),
        ("AWS/Lambda", "Errors"),
        ("AWS/Lambda", "IteratorAge"),
        ("AWS/Lambda", "Invocations"),
        ("AWS/ECS", "CPUUtilization"),
        ("AWS/ECS", "MemoryUtilization"),
        ("AWS/ECS", "CPUReservation"),
        ("AWS/ECS", "MemoryReservation"),
        ("AWS/ECS", "RegisteredContainerInstanceCount"),
        ("ECS/ContainerInsights", "RunningTaskCount"),
        ("ECS/ContainerInsights", "PendingTaskCount"),
        ("ECS/ContainerInsights", "ServiceCount"),
        ("EKS/ContainerInsights", "node_cpu_utilization"),
        ("EKS/ContainerInsights", "node_memory_utilization"),
        ("EKS/ContainerInsights", "pod_memory_utilization"),
        ("EKS/ContainerInsights", "cluster_node_count"),
        ("EKS/ContainerInsights", "pod_response_time"),
        ("EKS/ContainerInsights", "cluster_failed_node_count"),
        ("AWS/ApplicationELB", "ProcessedBytes"),
        ("AWS/ApplicationELB", "ActiveConnectionCount"),
        ("AWS/ApplicationELB", "UnHealthyHostCount"),
        ("AWS/ApplicationELB", "TargetResponseTime"),
        ("AWS/ApplicationELB", "HTTPCode_Target_5XX"),
        ("AWS/ApplicationELB", "RequestCount"),
        ("AWS/ApplicationELB", "SpilloverCount"),
        ("AWS/ApplicationELB", "RejectedConnectionCount"),
        ("AWS/ApiGateway", "Count"),
        ("AWS/ApiGateway", "DataProcessed"),
        ("AWS/ApiGateway", "CacheHitCount"),
        ("AWS/ApiGateway", "CacheMissCount"),
        ("AWS/ApiGateway", "5XXError"),
        ("AWS/ApiGateway", "IntegrationLatency"),
        ("AWS/ApiGateway", "Latency"),
        ("AWS/CloudFront", "Requests"),
        ("AWS/CloudFront", "BytesDownloaded"),
        ("AWS/CloudFront", "BytesUploaded"),
        ("AWS/CloudFront", "OriginLatency"),
        ("AWS/CloudFront", "5xxErrorRate"),
        ("AWS/S3", "AllRequests"),
        ("AWS/S3", "5xxErrors"),
        ("AWS/S3", "FirstByteLatency"),
        ("AWS/S3", "TotalRequestLatency"),
        ("AWS/DynamoDB", "ConsumedReadCapacityUnits"),
        ("AWS/DynamoDB", "ConsumedWriteCapacityUnits"),
        ("AWS/DynamoDB", "SuccessfulRequestLatency"),
        ("AWS/DynamoDB", "ThrottledRequests"),
        ("AWS/Logs", "IncomingLogEvents"),
        ("AWS/Logs", "ThrottleEvents"),
        ("AWS/Backup", "NumberOfBackupJobsFailed"),
        ("AWS/Backup", "SnapshotStorageUsed"),
        ("AWS/Backup", "BackupRetentionPeriodStorageUsed"),
        ("AWS/Route53", "DNSResolutionTime"),
        ("AWS/SQS", "ApproximateNumberOfMessagesVisible"),
        ("AWS/SQS", "ApproximateAgeOfOldestMessage"),
        ("AWS/SQS", "NumberOfMessagesDeleted"),
        ("CWAgent", "mem_used_percent"),
        ("CWAgent", "disk_used_percent"),
        ("AWS/CertificateManager", "DaysToExpiry"),
    }


def write_alarm_states(rds_client, alarm_records, cluster_arn, secret_arn, database):
    """
    Write alarm state records to Aurora PostgreSQL using RDS Data API.

    Each 5-minute collection cycle records the current state as a new row
    (different collected_at), preserving alarm state history over time.
    The ON CONFLICT clause handles duplicate writes from retries within
    the same collection cycle.

    Uses batch_execute_statement with INSERT ON CONFLICT for idempotent upserts.
    Splits into sub-batches of 1000 (RDS Data API limit per call).

    Args:
        rds_client: boto3 RDS Data API client.
        alarm_records: List of alarm record dicts with keys: collected_at,
            account_id, alarm_name, namespace, metric_name, dimensions
            (JSON string), resource_id, state, state_reason, state_updated_at.
        cluster_arn: Aurora cluster ARN.
        secret_arn: Secrets Manager ARN for DB credentials.
        database: Database name.
    """
    if not alarm_records:
        return

    sql = """
        INSERT INTO alarm_states
            (collected_at, account_id, alarm_name, namespace, metric_name,
             dimensions, resource_id, state, state_reason, state_updated_at)
        VALUES
            (CAST(:collected_at AS TIMESTAMP), :account_id, :alarm_name, :namespace, :metric_name,
             CAST(:dimensions AS JSONB), :resource_id, :state, :state_reason, CAST(:state_updated_at AS TIMESTAMP))
        ON CONFLICT (collected_at, account_id, alarm_name)
        DO UPDATE SET state = EXCLUDED.state,
                      state_reason = EXCLUDED.state_reason,
                      state_updated_at = EXCLUDED.state_updated_at
    """

    # Build parameter sets for all alarm records
    parameter_sets = [_build_alarm_params(record) for record in alarm_records]

    # RDS Data API batch_execute_statement limit is 1000 parameter sets per call
    batch_size = 1000
    total_written = 0

    for i in range(0, len(parameter_sets), batch_size):
        sub_batch = parameter_sets[i : i + batch_size]
        try:
            rds_client.batch_execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=database,
                sql=sql,
                parameterSets=sub_batch,
            )
            total_written += len(sub_batch)
        except ClientError as e:
            logger.error(
                f"RDS Data API batch_execute_statement failed for alarm_states: "
                f"{e.response['Error']['Code']} - {e.response['Error']['Message']} "
                f"(batch offset={i}, size={len(sub_batch)})"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error writing alarm states batch (offset={i}, "
                f"size={len(sub_batch)}): {e}"
            )

    logger.info(f"Wrote {total_written}/{len(alarm_records)} alarm state records to Aurora")


def _build_alarm_params(record):
    """
    Convert an alarm record dict to an RDS Data API parameter set.

    Args:
        record: Dict with keys: collected_at, account_id, alarm_name,
            namespace, metric_name, dimensions, resource_id, state,
            state_reason, state_updated_at.

    Returns:
        List of parameter dicts for batch_execute_statement.
    """
    return [
        {"name": "collected_at", "value": {"stringValue": str(record.get("collected_at", ""))}},
        {"name": "account_id", "value": {"stringValue": str(record.get("account_id", ""))}},
        {"name": "alarm_name", "value": {"stringValue": str(record.get("alarm_name", ""))}},
        {"name": "namespace", "value": {"stringValue": str(record.get("namespace", ""))}},
        {"name": "metric_name", "value": {"stringValue": str(record.get("metric_name", ""))}},
        {"name": "dimensions", "value": {"stringValue": str(record.get("dimensions", "{}"))}},
        {"name": "resource_id", "value": {"stringValue": str(record.get("resource_id", ""))}},
        {"name": "state", "value": {"stringValue": str(record.get("state", ""))}},
        {"name": "state_reason", "value": {"stringValue": str(record.get("state_reason", ""))}},
        {"name": "state_updated_at", "value": {"stringValue": str(record.get("state_updated_at", ""))}},
    ]
