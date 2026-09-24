"""Unit tests for discover_resources function."""

import unittest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from metric_collector import discover_resources


class TestDiscoverResources(unittest.TestCase):
    """Tests for discover_resources with mocked CloudWatch client."""

    def _make_paginator(self, pages):
        """Helper to create a mock paginator returning given pages."""
        paginator = MagicMock()
        paginator.paginate.return_value = pages
        return paginator

    def test_single_account_single_metric(self):
        """Discovers a single metric from one account."""
        cw_client = MagicMock()
        pages = [
            {
                "Metrics": [
                    {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [
                            {"Name": "InstanceId", "Value": "i-abc123"}
                        ],
                    }
                ]
            }
        ]
        cw_client.get_paginator.return_value = self._make_paginator(pages)

        result = discover_resources(cw_client, "AWS/EC2", ["123456789012"])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["namespace"], "AWS/EC2")
        self.assertEqual(result[0]["metric_name"], "CPUUtilization")
        self.assertEqual(result[0]["dimensions"], [{"Name": "InstanceId", "Value": "i-abc123"}])
        self.assertEqual(result[0]["account_id"], "123456789012")

        # Verify paginator was called correctly
        cw_client.get_paginator.assert_called_once_with("list_metrics")
        cw_client.get_paginator.return_value.paginate.assert_called_once_with(
            Namespace="AWS/EC2",
            OwningAccount="123456789012",
            IncludeLinkedAccounts=True,
        )

    def test_multiple_accounts(self):
        """Discovers metrics across multiple accounts."""
        cw_client = MagicMock()
        pages = [
            {
                "Metrics": [
                    {
                        "Namespace": "AWS/Lambda",
                        "MetricName": "Invocations",
                        "Dimensions": [
                            {"Name": "FunctionName", "Value": "my-func"}
                        ],
                    }
                ]
            }
        ]
        paginator = self._make_paginator(pages)
        cw_client.get_paginator.return_value = paginator

        result = discover_resources(cw_client, "AWS/Lambda", ["111111111111", "222222222222"])

        # Should have 2 results (one per account)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["account_id"], "111111111111")
        self.assertEqual(result[1]["account_id"], "222222222222")

    def test_pagination_multiple_pages(self):
        """Handles multiple pages of results from list_metrics."""
        cw_client = MagicMock()
        pages = [
            {
                "Metrics": [
                    {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name": "InstanceId", "Value": "i-001"}],
                    }
                ]
            },
            {
                "Metrics": [
                    {
                        "Namespace": "AWS/EC2",
                        "MetricName": "NetworkIn",
                        "Dimensions": [{"Name": "InstanceId", "Value": "i-002"}],
                    }
                ]
            },
        ]
        cw_client.get_paginator.return_value = self._make_paginator(pages)

        result = discover_resources(cw_client, "AWS/EC2", ["123456789012"])

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["metric_name"], "CPUUtilization")
        self.assertEqual(result[1]["metric_name"], "NetworkIn")

    def test_empty_dimensions(self):
        """Handles metrics with no dimensions."""
        cw_client = MagicMock()
        pages = [
            {
                "Metrics": [
                    {
                        "Namespace": "AWS/Lambda",
                        "MetricName": "ConcurrentExecutions",
                        "Dimensions": [],
                    }
                ]
            }
        ]
        cw_client.get_paginator.return_value = self._make_paginator(pages)

        result = discover_resources(cw_client, "AWS/Lambda", ["123456789012"])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["dimensions"], [])

    def test_client_error_skips_account(self):
        """Continues processing when a ClientError occurs for one account."""
        cw_client = MagicMock()

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(error_response, "ListMetrics")
        cw_client.get_paginator.return_value = paginator

        # Should not raise, just skip
        result = discover_resources(cw_client, "AWS/EC2", ["999999999999"])

        self.assertEqual(result, [])

    def test_unexpected_error_skips_account(self):
        """Continues processing when an unexpected exception occurs."""
        cw_client = MagicMock()

        paginator = MagicMock()
        paginator.paginate.side_effect = RuntimeError("Something went wrong")
        cw_client.get_paginator.return_value = paginator

        result = discover_resources(cw_client, "AWS/EC2", ["999999999999"])

        self.assertEqual(result, [])

    def test_multiple_dimensions(self):
        """Correctly extracts multiple dimensions from a metric."""
        cw_client = MagicMock()
        pages = [
            {
                "Metrics": [
                    {
                        "Namespace": "ECS/ContainerInsights",
                        "MetricName": "RunningTaskCount",
                        "Dimensions": [
                            {"Name": "ClusterName", "Value": "my-cluster"},
                            {"Name": "ServiceName", "Value": "my-service"},
                        ],
                    }
                ]
            }
        ]
        cw_client.get_paginator.return_value = self._make_paginator(pages)

        result = discover_resources(cw_client, "ECS/ContainerInsights", ["123456789012"])

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["dimensions"]), 2)
        self.assertEqual(result[0]["dimensions"][0], {"Name": "ClusterName", "Value": "my-cluster"})
        self.assertEqual(result[0]["dimensions"][1], {"Name": "ServiceName", "Value": "my-service"})

    def test_no_metrics_returned(self):
        """Returns empty list when no metrics are found."""
        cw_client = MagicMock()
        pages = [{"Metrics": []}]
        cw_client.get_paginator.return_value = self._make_paginator(pages)

        result = discover_resources(cw_client, "AWS/EC2", ["123456789012"])

        self.assertEqual(result, [])

    def test_account_id_converted_to_string(self):
        """Ensures integer account IDs are converted to strings."""
        cw_client = MagicMock()
        pages = [
            {
                "Metrics": [
                    {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name": "InstanceId", "Value": "i-123"}],
                    }
                ]
            }
        ]
        cw_client.get_paginator.return_value = self._make_paginator(pages)

        # Pass integer account ID
        result = discover_resources(cw_client, "AWS/EC2", [123456789012])

        self.assertEqual(result[0]["account_id"], "123456789012")
        # Verify OwningAccount was passed as string
        cw_client.get_paginator.return_value.paginate.assert_called_once_with(
            Namespace="AWS/EC2",
            OwningAccount="123456789012",
            IncludeLinkedAccounts=True,
        )


if __name__ == "__main__":
    unittest.main()
