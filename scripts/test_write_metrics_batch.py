"""Unit tests for write_metrics_batch function."""

import unittest
from unittest.mock import MagicMock, call, patch
from botocore.exceptions import ClientError

from metric_collector import write_metrics_batch, _build_metric_params


class TestBuildMetricParams(unittest.TestCase):
    """Tests for _build_metric_params helper."""

    def test_builds_correct_parameter_set(self):
        """Builds a properly formatted RDS Data API parameter set."""
        metric = {
            "collected_at": "2025-01-15T10:00:00+00:00",
            "account_id": "123456789012",
            "region": "ap-southeast-1",
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
            "dimensions": '[{"Name": "InstanceId", "Value": "i-abc123"}]',
            "resource_id": "i-abc123",
            "statistic": "Average",
            "value": 42.5,
            "unit": "Percent",
            "category": "capacity",
        }

        params = _build_metric_params(metric)

        self.assertEqual(len(params), 11)
        # Verify each parameter name and type
        param_dict = {p["name"]: p["value"] for p in params}
        self.assertEqual(param_dict["collected_at"], {"stringValue": "2025-01-15T10:00:00+00:00"})
        self.assertEqual(param_dict["account_id"], {"stringValue": "123456789012"})
        self.assertEqual(param_dict["region"], {"stringValue": "ap-southeast-1"})
        self.assertEqual(param_dict["namespace"], {"stringValue": "AWS/EC2"})
        self.assertEqual(param_dict["metric_name"], {"stringValue": "CPUUtilization"})
        self.assertEqual(param_dict["dimensions"], {"stringValue": '[{"Name": "InstanceId", "Value": "i-abc123"}]'})
        self.assertEqual(param_dict["resource_id"], {"stringValue": "i-abc123"})
        self.assertEqual(param_dict["statistic"], {"stringValue": "Average"})
        self.assertEqual(param_dict["value"], {"doubleValue": 42.5})
        self.assertEqual(param_dict["unit"], {"stringValue": "Percent"})
        self.assertEqual(param_dict["category"], {"stringValue": "capacity"})

    def test_handles_missing_keys_with_defaults(self):
        """Uses defaults for missing metric dict keys."""
        metric = {}
        params = _build_metric_params(metric)

        param_dict = {p["name"]: p["value"] for p in params}
        self.assertEqual(param_dict["collected_at"], {"stringValue": ""})
        self.assertEqual(param_dict["region"], {"stringValue": "ap-southeast-1"})
        self.assertEqual(param_dict["dimensions"], {"stringValue": "{}"})
        self.assertEqual(param_dict["value"], {"doubleValue": 0.0})


class TestWriteMetricsBatch(unittest.TestCase):
    """Tests for write_metrics_batch function."""

    def _make_metric(self, index=0):
        """Helper to create a sample metric dict."""
        return {
            "collected_at": f"2025-01-15T10:{index:02d}:00+00:00",
            "account_id": "123456789012",
            "region": "ap-southeast-1",
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
            "dimensions": '[{"Name": "InstanceId", "Value": "i-abc123"}]',
            "resource_id": f"i-abc{index:03d}",
            "statistic": "Average",
            "value": 50.0 + index,
            "unit": "Percent",
            "category": "capacity",
        }

    def test_empty_metrics_returns_early(self):
        """Does not call RDS when metrics list is empty."""
        rds_client = MagicMock()
        write_metrics_batch(rds_client, [], "cluster-arn", "secret-arn", "view360")
        rds_client.batch_execute_statement.assert_not_called()

    def test_single_batch_under_1000(self):
        """Writes a small batch in a single API call."""
        rds_client = MagicMock()
        metrics = [self._make_metric(i) for i in range(5)]

        write_metrics_batch(rds_client, metrics, "cluster-arn", "secret-arn", "view360")

        rds_client.batch_execute_statement.assert_called_once()
        call_kwargs = rds_client.batch_execute_statement.call_args[1]
        self.assertEqual(call_kwargs["resourceArn"], "cluster-arn")
        self.assertEqual(call_kwargs["secretArn"], "secret-arn")
        self.assertEqual(call_kwargs["database"], "view360")
        self.assertIn("INSERT INTO cloudwatch_metrics", call_kwargs["sql"])
        self.assertIn("ON CONFLICT", call_kwargs["sql"])
        self.assertEqual(len(call_kwargs["parameterSets"]), 5)

    def test_splits_into_sub_batches_of_1000(self):
        """Splits metrics into sub-batches when exceeding 1000."""
        rds_client = MagicMock()
        metrics = [self._make_metric(i % 60) for i in range(2500)]

        write_metrics_batch(rds_client, metrics, "cluster-arn", "secret-arn", "view360")

        # 2500 metrics -> 3 batches: 1000 + 1000 + 500
        self.assertEqual(rds_client.batch_execute_statement.call_count, 3)
        calls = rds_client.batch_execute_statement.call_args_list
        self.assertEqual(len(calls[0][1]["parameterSets"]), 1000)
        self.assertEqual(len(calls[1][1]["parameterSets"]), 1000)
        self.assertEqual(len(calls[2][1]["parameterSets"]), 500)

    def test_client_error_logs_and_continues(self):
        """Continues processing remaining batches on ClientError."""
        rds_client = MagicMock()
        metrics = [self._make_metric(i % 60) for i in range(1500)]

        # First call fails, second succeeds
        error_response = {"Error": {"Code": "BadRequestException", "Message": "SQL error"}}
        rds_client.batch_execute_statement.side_effect = [
            ClientError(error_response, "BatchExecuteStatement"),
            MagicMock(),
        ]

        write_metrics_batch(rds_client, metrics, "cluster-arn", "secret-arn", "view360")

        # Both sub-batches should be attempted
        self.assertEqual(rds_client.batch_execute_statement.call_count, 2)

    def test_unexpected_error_logs_and_continues(self):
        """Continues processing remaining batches on unexpected errors."""
        rds_client = MagicMock()
        metrics = [self._make_metric(i % 60) for i in range(1500)]

        # First call raises unexpected error, second succeeds
        rds_client.batch_execute_statement.side_effect = [
            RuntimeError("Connection lost"),
            MagicMock(),
        ]

        write_metrics_batch(rds_client, metrics, "cluster-arn", "secret-arn", "view360")

        self.assertEqual(rds_client.batch_execute_statement.call_count, 2)

    def test_sql_uses_upsert_pattern(self):
        """SQL statement uses INSERT ON CONFLICT DO UPDATE for idempotency."""
        rds_client = MagicMock()
        metrics = [self._make_metric()]

        write_metrics_batch(rds_client, metrics, "cluster-arn", "secret-arn", "view360")

        sql = rds_client.batch_execute_statement.call_args[1]["sql"]
        self.assertIn("ON CONFLICT", sql)
        self.assertIn("DO UPDATE SET value = EXCLUDED.value", sql)
        self.assertIn("CAST(:dimensions AS JSONB)", sql)


if __name__ == "__main__":
    unittest.main()
