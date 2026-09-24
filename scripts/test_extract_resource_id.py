"""Unit tests for extract_resource_id function."""

import unittest

from metric_collector import extract_resource_id


class TestExtractResourceId(unittest.TestCase):
    """Tests for extract_resource_id namespace-to-primary-dimension mapping."""

    def test_ec2_instance_id(self):
        """Extracts InstanceId for AWS/EC2 namespace."""
        dimensions = [{"Name": "InstanceId", "Value": "i-0abc123def456"}]
        result = extract_resource_id(dimensions, "AWS/EC2")
        self.assertEqual(result, "i-0abc123def456")

    def test_rds_db_instance_identifier(self):
        """Extracts DBInstanceIdentifier for AWS/RDS namespace."""
        dimensions = [{"Name": "DBInstanceIdentifier", "Value": "my-database"}]
        result = extract_resource_id(dimensions, "AWS/RDS")
        self.assertEqual(result, "my-database")

    def test_lambda_function_name(self):
        """Extracts FunctionName for AWS/Lambda namespace."""
        dimensions = [{"Name": "FunctionName", "Value": "my-function"}]
        result = extract_resource_id(dimensions, "AWS/Lambda")
        self.assertEqual(result, "my-function")

    def test_alb_load_balancer(self):
        """Extracts LoadBalancer for AWS/ApplicationELB namespace."""
        dimensions = [{"Name": "LoadBalancer", "Value": "app/my-alb/abc123"}]
        result = extract_resource_id(dimensions, "AWS/ApplicationELB")
        self.assertEqual(result, "app/my-alb/abc123")

    def test_api_gateway_api_name(self):
        """Extracts ApiName for AWS/ApiGateway namespace."""
        dimensions = [{"Name": "ApiName", "Value": "my-api"}]
        result = extract_resource_id(dimensions, "AWS/ApiGateway")
        self.assertEqual(result, "my-api")

    def test_ecs_cluster_name(self):
        """Extracts ClusterName for AWS/ECS namespace."""
        dimensions = [
            {"Name": "ClusterName", "Value": "my-cluster"},
            {"Name": "ServiceName", "Value": "my-service"},
        ]
        result = extract_resource_id(dimensions, "AWS/ECS")
        self.assertEqual(result, "my-cluster")

    def test_ecs_container_insights_cluster_name(self):
        """Extracts ClusterName for ECS/ContainerInsights namespace."""
        dimensions = [{"Name": "ClusterName", "Value": "ecs-cluster"}]
        result = extract_resource_id(dimensions, "ECS/ContainerInsights")
        self.assertEqual(result, "ecs-cluster")

    def test_eks_container_insights_cluster_name(self):
        """Extracts ClusterName for EKS/ContainerInsights namespace."""
        dimensions = [{"Name": "ClusterName", "Value": "eks-cluster"}]
        result = extract_resource_id(dimensions, "EKS/ContainerInsights")
        self.assertEqual(result, "eks-cluster")

    def test_cloudfront_distribution_id(self):
        """Extracts DistributionId for AWS/CloudFront namespace."""
        dimensions = [{"Name": "DistributionId", "Value": "E1234ABCDEF"}]
        result = extract_resource_id(dimensions, "AWS/CloudFront")
        self.assertEqual(result, "E1234ABCDEF")

    def test_s3_bucket_name(self):
        """Extracts BucketName for AWS/S3 namespace."""
        dimensions = [
            {"Name": "BucketName", "Value": "my-bucket"},
            {"Name": "FilterId", "Value": "EntireBucket"},
        ]
        result = extract_resource_id(dimensions, "AWS/S3")
        self.assertEqual(result, "my-bucket")

    def test_dynamodb_table_name(self):
        """Extracts TableName for AWS/DynamoDB namespace."""
        dimensions = [{"Name": "TableName", "Value": "my-table"}]
        result = extract_resource_id(dimensions, "AWS/DynamoDB")
        self.assertEqual(result, "my-table")

    def test_sqs_queue_name(self):
        """Extracts QueueName for AWS/SQS namespace."""
        dimensions = [{"Name": "QueueName", "Value": "my-queue"}]
        result = extract_resource_id(dimensions, "AWS/SQS")
        self.assertEqual(result, "my-queue")

    def test_cwagent_instance_id(self):
        """Extracts InstanceId for CWAgent namespace."""
        dimensions = [
            {"Name": "InstanceId", "Value": "i-0abc123def456"},
            {"Name": "device", "Value": "xvda1"},
        ]
        result = extract_resource_id(dimensions, "CWAgent")
        self.assertEqual(result, "i-0abc123def456")

    def test_logs_log_group_name(self):
        """Extracts LogGroupName for AWS/Logs namespace."""
        dimensions = [{"Name": "LogGroupName", "Value": "/aws/lambda/my-func"}]
        result = extract_resource_id(dimensions, "AWS/Logs")
        self.assertEqual(result, "/aws/lambda/my-func")

    def test_backup_resource_type(self):
        """Extracts ResourceType for AWS/Backup namespace."""
        dimensions = [{"Name": "ResourceType", "Value": "EBS"}]
        result = extract_resource_id(dimensions, "AWS/Backup")
        self.assertEqual(result, "EBS")

    def test_certificate_manager_arn(self):
        """Extracts CertificateArn for AWS/CertificateManager namespace."""
        dimensions = [
            {"Name": "CertificateArn", "Value": "arn:aws:acm:us-east-1:123456789012:certificate/abc"}
        ]
        result = extract_resource_id(dimensions, "AWS/CertificateManager")
        self.assertEqual(result, "arn:aws:acm:us-east-1:123456789012:certificate/abc")

    def test_route53_health_check_id(self):
        """Extracts HealthCheckId for AWS/Route53 namespace."""
        dimensions = [{"Name": "HealthCheckId", "Value": "hc-12345"}]
        result = extract_resource_id(dimensions, "AWS/Route53")
        self.assertEqual(result, "hc-12345")

    def test_unknown_namespace_falls_back_to_first_dimension(self):
        """Falls back to first dimension value for unknown namespaces."""
        dimensions = [
            {"Name": "SomeCustomDim", "Value": "custom-value"},
            {"Name": "AnotherDim", "Value": "other-value"},
        ]
        result = extract_resource_id(dimensions, "Custom/Unknown")
        self.assertEqual(result, "custom-value")

    def test_empty_dimensions_returns_empty_string(self):
        """Returns empty string when dimensions list is empty."""
        result = extract_resource_id([], "AWS/EC2")
        self.assertEqual(result, "")

    def test_none_dimensions_returns_empty_string(self):
        """Returns empty string when dimensions is None (falsy)."""
        result = extract_resource_id(None, "AWS/EC2")
        self.assertEqual(result, "")

    def test_primary_dimension_not_in_dimensions_falls_back(self):
        """Falls back to first dimension when primary dimension is not present."""
        dimensions = [{"Name": "AutoScalingGroupName", "Value": "my-asg"}]
        result = extract_resource_id(dimensions, "AWS/EC2")
        self.assertEqual(result, "my-asg")

    def test_primary_dimension_not_first_in_list(self):
        """Finds primary dimension even when it's not the first element."""
        dimensions = [
            {"Name": "ServiceName", "Value": "my-service"},
            {"Name": "ClusterName", "Value": "my-cluster"},
        ]
        result = extract_resource_id(dimensions, "AWS/ECS")
        self.assertEqual(result, "my-cluster")


if __name__ == "__main__":
    unittest.main()
