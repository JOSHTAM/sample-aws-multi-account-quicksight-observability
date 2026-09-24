"""Unit tests for collect_alarm_states function."""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from metric_collector import collect_alarm_states


class TestCollectAlarmStates(unittest.TestCase):
    """Tests for collect_alarm_states with mocked CloudWatch client."""

    def _make_alarm(
        self,
        name="test-alarm",
        namespace="AWS/EC2",
        metric_name="CPUUtilization",
        dimensions=None,
        state="OK",
        state_reason="Threshold not crossed",
        alarm_arn="arn:aws:cloudwatch:ap-southeast-1:123456789012:alarm:test-alarm",
        state_updated=None,
    ):
        """Helper to create a mock alarm dict."""
        if dimensions is None:
            dimensions = [{"Name": "InstanceId", "Value": "i-abc123"}]
        if state_updated is None:
            state_updated = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        return {
            "AlarmName": name,
            "AlarmArn": alarm_arn,
            "Namespace": namespace,
            "MetricName": metric_name,
            "Dimensions": dimensions,
            "StateValue": state,
            "StateReason": state_reason,
            "StateUpdatedTimestamp": state_updated,
        }

    @patch("metric_collector.boto3.client")
    @patch("metric_collector._get_l2_dashboard_metrics")
    def test_collects_l2_alarm(self, mock_get_metrics, mock_boto_client):
        """Collects alarms matching L2 dashboard metrics."""
        mock_get_metrics.return_value = {("AWS/EC2", "CPUUtilization")}

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw
        mock_cw.describe_alarms.return_value = {
            "MetricAlarms": [self._make_alarm()],
        }

        result = collect_alarm_states(MagicMock(), ["123456789012"])

        self.assertEqual(len(result), 1)
        record = result[0]
        self.assertEqual(record["alarm_name"], "test-alarm")
        self.assertEqual(record["namespace"], "AWS/EC2")
        self.assertEqual(record["metric_name"], "CPUUtilization")
        self.assertEqual(record["state"], "OK")
        self.assertEqual(record["state_reason"], "Threshold not crossed")
        self.assertEqual(record["resource_id"], "i-abc123")
        self.assertEqual(record["account_id"], "123456789012")
        self.assertIn("collected_at", record)
        # Dimensions should be JSON string
        dims = json.loads(record["dimensions"])
        self.assertEqual(dims, [{"Name": "InstanceId", "Value": "i-abc123"}])

    @patch("metric_collector.boto3.client")
    @patch("metric_collector._get_l2_dashboard_metrics")
    def test_filters_non_l2_alarms(self, mock_get_metrics, mock_boto_client):
        """Excludes alarms not matching L2 dashboard metrics."""
        mock_get_metrics.return_value = {("AWS/EC2", "CPUUtilization")}

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw
        mock_cw.describe_alarms.return_value = {
            "MetricAlarms": [
                self._make_alarm(namespace="AWS/SomeOther", metric_name="CustomMetric"),
                self._make_alarm(name="ec2-alarm", namespace="AWS/EC2", metric_name="CPUUtilization"),
            ],
        }

        result = collect_alarm_states(MagicMock(), ["123456789012"])

        # Only the EC2 CPUUtilization alarm should be included
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["alarm_name"], "ec2-alarm")

    @patch("metric_collector.boto3.client")
    @patch("metric_collector._get_l2_dashboard_metrics")
    def test_pagination(self, mock_get_metrics, mock_boto_client):
        """Handles pagination via NextToken."""
        mock_get_metrics.return_value = {("AWS/Lambda", "Errors")}

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw
        mock_cw.describe_alarms.side_effect = [
            {
                "MetricAlarms": [
                    self._make_alarm(
                        name="alarm-1",
                        namespace="AWS/Lambda",
                        metric_name="Errors",
                        dimensions=[{"Name": "FunctionName", "Value": "func-a"}],
                    )
                ],
                "NextToken": "page2",
            },
            {
                "MetricAlarms": [
                    self._make_alarm(
                        name="alarm-2",
                        namespace="AWS/Lambda",
                        metric_name="Errors",
                        dimensions=[{"Name": "FunctionName", "Value": "func-b"}],
                    )
                ],
            },
        ]

        result = collect_alarm_states(MagicMock(), ["123456789012"])

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["alarm_name"], "alarm-1")
        self.assertEqual(result[1]["alarm_name"], "alarm-2")

    @patch("metric_collector.boto3.client")
    @patch("metric_collector._get_l2_dashboard_metrics")
    def test_client_error_returns_empty(self, mock_get_metrics, mock_boto_client):
        """Returns empty list and logs error on ClientError."""
        mock_get_metrics.return_value = {("AWS/EC2", "CPUUtilization")}

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw
        mock_cw.describe_alarms.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
            "DescribeAlarms",
        )

        result = collect_alarm_states(MagicMock(), ["123456789012"])

        self.assertEqual(result, [])

    @patch("metric_collector.boto3.client")
    @patch("metric_collector._get_l2_dashboard_metrics")
    def test_account_filtering(self, mock_get_metrics, mock_boto_client):
        """Filters out alarms from accounts not in the accounts list."""
        mock_get_metrics.return_value = {("AWS/EC2", "CPUUtilization")}

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw
        mock_cw.describe_alarms.return_value = {
            "MetricAlarms": [
                self._make_alarm(
                    name="alarm-ours",
                    alarm_arn="arn:aws:cloudwatch:ap-southeast-1:123456789012:alarm:alarm-ours",
                ),
                self._make_alarm(
                    name="alarm-other",
                    alarm_arn="arn:aws:cloudwatch:ap-southeast-1:999999999999:alarm:alarm-other",
                ),
            ],
        }

        result = collect_alarm_states(MagicMock(), ["123456789012"])

        # Only alarm from account 123456789012 should be included
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["alarm_name"], "alarm-ours")

    @patch("metric_collector.boto3.client")
    @patch("metric_collector._get_l2_dashboard_metrics")
    def test_state_updated_timestamp_formatting(self, mock_get_metrics, mock_boto_client):
        """Formats StateUpdatedTimestamp as ISO string."""
        mock_get_metrics.return_value = {("AWS/RDS", "ReadLatency")}

        ts = datetime(2025, 6, 20, 14, 0, 0, tzinfo=timezone.utc)
        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw
        mock_cw.describe_alarms.return_value = {
            "MetricAlarms": [
                self._make_alarm(
                    namespace="AWS/RDS",
                    metric_name="ReadLatency",
                    dimensions=[{"Name": "DBInstanceIdentifier", "Value": "my-db"}],
                    state_updated=ts,
                )
            ],
        }

        result = collect_alarm_states(MagicMock(), ["123456789012"])

        self.assertEqual(result[0]["state_updated_at"], "2025-06-20T14:00:00+00:00")
        self.assertEqual(result[0]["resource_id"], "my-db")


if __name__ == "__main__":
    unittest.main()
