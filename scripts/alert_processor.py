"""Executive Alerts Dashboard - Alert Processor Lambda"""
import boto3
import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

# Environment variables
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
QUICKSIGHT_URL = os.environ.get('QUICKSIGHT_DASHBOARD_URL', '')
CLUSTER_ARN = os.environ.get('AURORA_CLUSTER_ARN', '')
SECRET_ARN = os.environ.get('AURORA_SECRET_ARN', '')
DB_NAME = os.environ.get('DB_NAME', 'core')
REGION = os.environ.get('REGION', 'ap-southeast-1')

# Icons
SEVERITY_ICONS = {
    'Critical': '🔴',
    'High': '🟠',
    'Medium': '🟡',
    'Low': '🔵'
}


class SeverityClassifier:
    """Classifies alarm severity based on notification_rules table"""

    def __init__(self, rds_client):
        self.rds = rds_client
        self._rules_cache = None
        self._cache_time = None

    def _load_rules(self) -> List[Dict]:
        """Load notification rules from database"""
        # Cache rules for 5 minutes
        now = time.time()
        if self._rules_cache and self._cache_time and (now - self._cache_time) < 300:
            return self._rules_cache

        try:
            response = self.rds.execute_statement(
                resourceArn=CLUSTER_ARN,
                secretArn=SECRET_ARN,
                database=DB_NAME,
                sql="SELECT namespace, metric_name, threshold_min, threshold_max, severity FROM notification_rules WHERE is_active = true"
            )
            self._rules_cache = [
                {
                    'namespace': row[0]['stringValue'],
                    'metric_name': row[1].get('stringValue'),
                    'threshold_min': float(row[2]['stringValue']) if row[2].get('stringValue') else None,
                    'threshold_max': float(row[3]['stringValue']) if row[3].get('stringValue') else None,
                    'severity': row[4]['stringValue']
                }
                for row in response.get('records', [])
            ]
            self._cache_time = now
        except Exception as e:
            print(f"Warning: Could not load notification rules: {e}")
            self._rules_cache = []
            self._cache_time = now

        return self._rules_cache

    def classify(self, namespace: str, metric_name: str, threshold: Optional[float] = None) -> str:
        """Classify alarm severity. Returns 'Medium' as default when no rule matches."""
        rules = self._load_rules()

        for rule in rules:
            if rule['namespace'] == namespace:
                if rule['metric_name'] is None or rule['metric_name'] == metric_name:
                    # If threshold bounds are defined, check them
                    if threshold is not None:
                        if rule['threshold_min'] is not None and threshold < rule['threshold_min']:
                            continue
                        if rule['threshold_max'] is not None and threshold > rule['threshold_max']:
                            continue
                    return rule['severity']

        return 'Medium'  # Default severity


class ConsecutiveFailureDetector:
    """Detects 3+ consecutive canary failures"""

    def __init__(self, rds_client):
        self.rds = rds_client

    def has_consecutive_failures(self, canary_name: str, account_id: int) -> bool:
        """Returns True if the most recent 3+ runs are all FAILED"""
        try:
            response = self.rds.execute_statement(
                resourceArn=CLUSTER_ARN,
                secretArn=SECRET_ARN,
                database=DB_NAME,
                sql="""
                    SELECT cr.run_status FROM canary_runs cr
                    JOIN canaries c ON cr.canary_id = c.id
                    WHERE c.canary_name = :canary_name AND c.account_id = :account_id
                    ORDER BY cr.run_at DESC LIMIT 3
                """,
                parameters=[
                    {'name': 'canary_name', 'value': {'stringValue': canary_name}},
                    {'name': 'account_id', 'value': {'longValue': account_id}}
                ]
            )
            records = response.get('records', [])
            if len(records) < 3:
                return False
            return all(row[0]['stringValue'] == 'FAILED' for row in records)
        except Exception as e:
            print(f"Warning: Could not check canary failures for {canary_name}: {e}")
            return False


class SlackRateLimiter:
    """Enforces max 10 Slack messages per 5-minute sliding window"""
    MAX_MESSAGES = 10
    WINDOW_SECONDS = 300  # 5 minutes

    def __init__(self, rds_client):
        self.rds = rds_client

    def can_send(self) -> bool:
        """Check if we can send a message within the rate limit"""
        window_start = (datetime.now(timezone.utc) - timedelta(seconds=self.WINDOW_SECONDS)).isoformat()
        try:
            response = self.rds.execute_statement(
                resourceArn=CLUSTER_ARN,
                secretArn=SECRET_ARN,
                database=DB_NAME,
                sql="SELECT COUNT(*) FROM slack_notifications WHERE sent_at > :window_start::timestamp AND status = 'sent'",
                parameters=[{'name': 'window_start', 'value': {'stringValue': window_start}}]
            )
            count = response['records'][0][0]['longValue']
            return count < self.MAX_MESSAGES
        except Exception as e:
            print(f"Warning: Rate limiter check failed: {e}")
            return True  # Allow send on failure to not block critical alerts

    def record_send(self, alert_type: str, alert_id: str, severity: str, message_summary: str, status: str = 'sent') -> None:
        """Record a notification in the database for audit and rate limiting"""
        try:
            self.rds.execute_statement(
                resourceArn=CLUSTER_ARN,
                secretArn=SECRET_ARN,
                database=DB_NAME,
                sql="""INSERT INTO slack_notifications (alert_type, alert_id, severity, message_summary, status)
                       VALUES (:alert_type, :alert_id, :severity, :message_summary, :status)""",
                parameters=[
                    {'name': 'alert_type', 'value': {'stringValue': alert_type}},
                    {'name': 'alert_id', 'value': {'stringValue': alert_id or ''}},
                    {'name': 'severity', 'value': {'stringValue': severity or ''}},
                    {'name': 'message_summary', 'value': {'stringValue': (message_summary or '')[:500]}},
                    {'name': 'status', 'value': {'stringValue': status}}
                ]
            )
        except Exception as e:
            print(f"Warning: Could not record notification: {e}")


class SlackMessageFormatter:
    """Formats Slack Block Kit messages"""

    @staticmethod
    def format_alarm(alarm: Dict, account_name: str = '') -> Dict:
        severity = alarm.get('severity', 'Medium')
        icon = SEVERITY_ICONS.get(severity, '🟡')
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"{icon} CloudWatch Alarm: {severity}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Alarm:*\n{alarm.get('alarm_name', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Account:*\n{account_name or alarm.get('account_name', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Resource:*\n{alarm.get('resource_arn', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Namespace:*\n{alarm.get('namespace', 'N/A')}"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Reason:* {alarm.get('state_reason', 'N/A')[:200]}"}},
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": f"⏰ {alarm.get('state_updated_at', datetime.now(timezone.utc).isoformat())} | <{QUICKSIGHT_URL}|View Dashboard>"}
                ]}
            ]
        }

    @staticmethod
    def format_incident(incident: Dict, account_name: str = '') -> Dict:
        severity = incident.get('severity', 'P3')
        icon = '🔴' if severity in ['P1', 'P2'] else '🟠'
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"{icon} Incident: {severity} - {incident.get('title', 'Unknown')}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*Account:*\n{account_name or incident.get('account_name', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Service:*\n{incident.get('affected_service', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Start Time:*\n{incident.get('start_time', 'N/A')}"},
                ]},
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": f"<{QUICKSIGHT_URL}|View Dashboard>"}
                ]}
            ]
        }

    @staticmethod
    def format_canary_failure(canary: Dict, account_name: str = '') -> Dict:
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"🟠 Canary Failure: {canary.get('canary_name', 'Unknown')}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Canary:*\n{canary.get('canary_name', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Account:*\n{account_name or 'Unknown'}"},
                    {"type": "mrkdwn", "text": f"*Endpoint:*\n{canary.get('endpoint_url', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Failure Reason:*\n{canary.get('failure_reason', 'N/A')}"},
                ]},
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": f"3+ consecutive failures detected | <{QUICKSIGHT_URL}|View Dashboard>"}
                ]}
            ]
        }

    @staticmethod
    def format_grouped_summary(alerts: List[Dict]) -> Dict:
        """Format a summary message when rate limit is hit"""
        count = len(alerts)
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"⚠️ {count} Additional Alerts (Rate Limited)"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{count} additional alerts were grouped to prevent notification fatigue.* Check the dashboard for details."}},
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": f"<{QUICKSIGHT_URL}|View Dashboard>"}
                ]}
            ]
        }


class SlackDispatcher:
    """Sends Slack messages with retry logic"""
    MAX_RETRIES = 3
    BACKOFF_BASE = 1  # 1s, 4s, 16s

    @staticmethod
    def send(message: Dict) -> Tuple[bool, Optional[str]]:
        """Send a Slack message with exponential backoff retry"""
        if not SLACK_WEBHOOK_URL:
            return False, "SLACK_WEBHOOK_URL not configured"

        for attempt in range(SlackDispatcher.MAX_RETRIES):
            try:
                data = json.dumps(message).encode('utf-8')
                req = urllib.request.Request(
                    SLACK_WEBHOOK_URL,
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        return True, None
                    error = f"Slack API returned status {response.status}"
            except Exception as e:
                error = str(e)

            if attempt < SlackDispatcher.MAX_RETRIES - 1:
                wait = SlackDispatcher.BACKOFF_BASE * (4 ** attempt)  # 1, 4, 16
                time.sleep(wait)

        return False, error


def handler(event, context):
    """Main Lambda handler for Alert Processor"""
    rds_client = boto3.client('rds-data', region_name=REGION)

    classifier = SeverityClassifier(rds_client)
    failure_detector = ConsecutiveFailureDetector(rds_client)
    rate_limiter = SlackRateLimiter(rds_client)
    formatter = SlackMessageFormatter()

    source = event.get('source', '')
    pending_notifications = []

    # Route based on event source
    if source == 'receiver':
        # Batch processing from Receiver
        alarm_records = event.get('alarm_records', [])
        incident_records = event.get('incident_records', [])
        canary_records = event.get('canary_records', [])

        # Process alarms - classify severity and notify for Critical/High
        for alarm in alarm_records:
            if alarm.get('state') == 'ALARM':
                severity = classifier.classify(
                    alarm.get('namespace', ''),
                    alarm.get('metric_name', ''),
                    alarm.get('threshold')
                )
                alarm['severity'] = severity

                # Update severity in database
                try:
                    rds_client.execute_statement(
                        resourceArn=CLUSTER_ARN, secretArn=SECRET_ARN, database=DB_NAME,
                        sql="UPDATE alarms SET severity = :severity, updated_at = CURRENT_TIMESTAMP WHERE alarm_arn = :alarm_arn",
                        parameters=[
                            {'name': 'severity', 'value': {'stringValue': severity}},
                            {'name': 'alarm_arn', 'value': {'stringValue': alarm.get('alarm_arn', '')}}
                        ]
                    )
                except Exception as e:
                    print(f"Warning: Could not update alarm severity: {e}")

                if severity in ['Critical', 'High']:
                    pending_notifications.append(('alarm', alarm))

        # Process incidents - notify for P1/P2
        for incident in incident_records:
            if incident.get('severity') in ['P1', 'P2']:
                pending_notifications.append(('incident', incident))

        # Process canaries - check consecutive failures
        for canary in canary_records:
            # Get account_id from database for this canary
            try:
                response = rds_client.execute_statement(
                    resourceArn=CLUSTER_ARN, secretArn=SECRET_ARN, database=DB_NAME,
                    sql="SELECT account_id FROM canaries WHERE canary_name = :name LIMIT 1",
                    parameters=[{'name': 'name', 'value': {'stringValue': canary.get('canary_name', '')}}]
                )
                if response.get('records'):
                    account_id = response['records'][0][0]['longValue']
                    if failure_detector.has_consecutive_failures(canary.get('canary_name', ''), account_id):
                        pending_notifications.append(('canary', canary))
            except Exception as e:
                print(f"Warning: Could not check canary {canary.get('canary_name')}: {e}")

    elif source == 'aws.cloudwatch':
        # Real-time EventBridge alarm state change
        detail = event.get('detail', {})
        alarm_name = detail.get('alarmName', '')
        state = detail.get('state', {}).get('value', '')

        if state == 'ALARM':
            config = detail.get('configuration', {})
            metrics = config.get('metrics', [{}])
            metric_info = metrics[0] if metrics else {}
            metric_stat = metric_info.get('metricStat', {}).get('metric', {})

            namespace = metric_stat.get('namespace', '')
            metric_name = metric_stat.get('name', '')
            threshold = config.get('threshold')

            severity = classifier.classify(namespace, metric_name, threshold)

            alarm_record = {
                'alarm_arn': detail.get('alarmArn', ''),
                'alarm_name': alarm_name,
                'state': state,
                'state_reason': detail.get('state', {}).get('reason', ''),
                'state_updated_at': detail.get('state', {}).get('timestamp', ''),
                'namespace': namespace,
                'metric_name': metric_name,
                'threshold': threshold,
                'severity': severity,
                'resource_arn': '',
                'account_name': event.get('account', '')
            }

            # Upsert alarm record in database
            try:
                rds_client.execute_statement(
                    resourceArn=CLUSTER_ARN, secretArn=SECRET_ARN, database=DB_NAME,
                    sql="""INSERT INTO alarms (account_id, alarm_arn, alarm_name, state, state_reason, state_updated_at, metric_name, namespace, threshold, severity)
                           SELECT a.id, :alarm_arn, :alarm_name, :state, :state_reason, :state_updated_at, :metric_name, :namespace, :threshold, :severity
                           FROM accounts a WHERE a.account_id = :aws_account_id
                           ON CONFLICT (account_id, alarm_arn) DO UPDATE SET
                           state = EXCLUDED.state, state_reason = EXCLUDED.state_reason,
                           state_updated_at = EXCLUDED.state_updated_at, severity = EXCLUDED.severity,
                           updated_at = CURRENT_TIMESTAMP""",
                    parameters=[
                        {'name': 'alarm_arn', 'value': {'stringValue': alarm_record['alarm_arn']}},
                        {'name': 'alarm_name', 'value': {'stringValue': alarm_name}},
                        {'name': 'state', 'value': {'stringValue': state}},
                        {'name': 'state_reason', 'value': {'stringValue': alarm_record['state_reason']}},
                        {'name': 'state_updated_at', 'value': {'stringValue': alarm_record['state_updated_at']}},
                        {'name': 'metric_name', 'value': {'stringValue': metric_name}},
                        {'name': 'namespace', 'value': {'stringValue': namespace}},
                        {'name': 'threshold', 'value': {'stringValue': str(threshold) if threshold else '0'}},
                        {'name': 'severity', 'value': {'stringValue': severity}},
                        {'name': 'aws_account_id', 'value': {'stringValue': event.get('account', '')}}
                    ]
                )
            except Exception as e:
                print(f"Warning: Could not upsert alarm from EventBridge: {e}")

            if severity in ['Critical', 'High']:
                pending_notifications.append(('alarm', alarm_record))

    # Send notifications with rate limiting
    grouped = []
    for alert_type, alert_data in pending_notifications:
        if rate_limiter.can_send():
            # Format message
            if alert_type == 'alarm':
                message = formatter.format_alarm(alert_data)
            elif alert_type == 'incident':
                message = formatter.format_incident(alert_data)
            elif alert_type == 'canary':
                message = formatter.format_canary_failure(alert_data)
            else:
                continue

            # Send
            success, error = SlackDispatcher.send(message)
            status = 'sent' if success else 'failed'
            rate_limiter.record_send(
                alert_type=alert_type,
                alert_id=alert_data.get('alarm_arn') or alert_data.get('incident_id') or alert_data.get('canary_name', ''),
                severity=alert_data.get('severity', ''),
                message_summary=alert_data.get('alarm_name') or alert_data.get('title') or alert_data.get('canary_name', ''),
                status=status
            )
            if not success:
                print(f"Failed to send Slack notification after retries: {error}")
        else:
            grouped.append(alert_data)

    # Send grouped summary if any were rate-limited
    if grouped:
        summary_message = formatter.format_grouped_summary(grouped)
        SlackDispatcher.send(summary_message)
        rate_limiter.record_send(
            alert_type='grouped',
            alert_id='',
            severity='',
            message_summary=f"{len(grouped)} alerts grouped",
            status='grouped'
        )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': len(pending_notifications),
            'sent': len(pending_notifications) - len(grouped),
            'grouped': len(grouped)
        })
    }


def lambda_handler(event, context):
    """Lambda entry point"""
    return handler(event, context)
