#!/bin/bash
###############################################################################
# deploy_metrics_dashboard.sh
#
# Deploys the Real-Time Metrics Dashboard infrastructure:
#   1. Packages Lambda functions into zip files
#   2. Uploads configuration files to S3
#   3. Uploads Lambda zip packages to S3
#   4. Deploys/updates the CloudFormation stack
#
# Usage:
#   ./deploy_metrics_dashboard.sh -b <s3-bucket-name> -s <stack-name> [-r <region>]
#
# Parameters:
#   -b  S3 bucket name for artifacts (required)
#   -s  CloudFormation stack name (required)
#   -r  AWS region (default: ap-southeast-1)
#
# Examples:
#   ./deploy_metrics_dashboard.sh -b my-analytics-bucket -s A360-Analytics
#   ./deploy_metrics_dashboard.sh -b my-analytics-bucket -s A360-Analytics -r ap-southeast-1
#
# Prerequisites:
#   - AWS CLI v2 installed and configured
#   - Appropriate IAM permissions for S3, CloudFormation, Lambda, IAM, Events
#   - zip utility available
###############################################################################

set -e

# ---------------------------
# Default values
# ---------------------------
REGION="ap-southeast-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${SCRIPT_DIR}/.build"

# ---------------------------
# Parse arguments
# ---------------------------
usage() {
    echo "Usage: $0 -b <s3-bucket-name> -s <stack-name> [-r <region>]"
    echo ""
    echo "Options:"
    echo "  -b  S3 bucket name for Lambda code and config artifacts (required)"
    echo "  -s  CloudFormation stack name (required)"
    echo "  -r  AWS region (default: ap-southeast-1)"
    echo "  -h  Show this help message"
    exit 1
}

while getopts "b:s:r:h" opt; do
    case ${opt} in
        b) S3_BUCKET="${OPTARG}" ;;
        s) STACK_NAME="${OPTARG}" ;;
        r) REGION="${OPTARG}" ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [ -z "${S3_BUCKET}" ] || [ -z "${STACK_NAME}" ]; then
    echo "Error: S3 bucket name (-b) and stack name (-s) are required."
    usage
fi

echo "============================================="
echo " Real-Time Metrics Dashboard Deployment"
echo "============================================="
echo " S3 Bucket:  ${S3_BUCKET}"
echo " Stack Name: ${STACK_NAME}"
echo " Region:     ${REGION}"
echo " Script Dir: ${SCRIPT_DIR}"
echo "============================================="
echo ""

# ---------------------------
# Step 1: Package Lambda functions
# ---------------------------
echo "[1/4] Packaging Lambda functions..."

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Package metric_collector.py
echo "  - Packaging metric_collector.py → lambda/metric_collector.zip"
cd "${SCRIPT_DIR}"
zip -j "${BUILD_DIR}/metric_collector.zip" metric_collector.py
cd "${PROJECT_ROOT}"

# Package data_retention.py
echo "  - Packaging data_retention.py → lambda/data_retention.zip"
cd "${SCRIPT_DIR}"
zip -j "${BUILD_DIR}/data_retention.zip" data_retention.py
cd "${PROJECT_ROOT}"

echo "  ✓ Lambda packages created in ${BUILD_DIR}/"
echo ""

# ---------------------------
# Step 2: Upload config files to S3
# ---------------------------
echo "[2/4] Uploading configuration files to S3..."

echo "  - Uploading metric_definitions.json → s3://${S3_BUCKET}/config/metric_definitions.json"
aws s3 cp "${SCRIPT_DIR}/metric_definitions.json" \
    "s3://${S3_BUCKET}/config/metric_definitions.json" \
    --region "${REGION}"

echo "  - Uploading exclude.json → s3://${S3_BUCKET}/config/exclude.json"
aws s3 cp "${SCRIPT_DIR}/exclude.json" \
    "s3://${S3_BUCKET}/config/exclude.json" \
    --region "${REGION}"

echo "  ✓ Configuration files uploaded"
echo ""

# ---------------------------
# Step 3: Upload Lambda zips to S3
# ---------------------------
echo "[3/4] Uploading Lambda packages to S3..."

echo "  - Uploading metric_collector.zip → s3://${S3_BUCKET}/lambda/metric_collector.zip"
aws s3 cp "${BUILD_DIR}/metric_collector.zip" \
    "s3://${S3_BUCKET}/lambda/metric_collector.zip" \
    --region "${REGION}"

echo "  - Uploading data_retention.zip → s3://${S3_BUCKET}/lambda/data_retention.zip"
aws s3 cp "${BUILD_DIR}/data_retention.zip" \
    "s3://${S3_BUCKET}/lambda/data_retention.zip" \
    --region "${REGION}"

echo "  ✓ Lambda packages uploaded"
echo ""

# ---------------------------
# Step 4: Deploy CloudFormation stack
# ---------------------------
echo "[4/4] Deploying CloudFormation stack..."

TEMPLATE_FILE="${PROJECT_ROOT}/cloudformation/A360-Analytics.yaml"

if [ ! -f "${TEMPLATE_FILE}" ]; then
    echo "Error: CloudFormation template not found at ${TEMPLATE_FILE}"
    exit 1
fi

aws cloudformation deploy \
    --template-file "${TEMPLATE_FILE}" \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --parameter-overrides S3BucketName="${S3_BUCKET}" \
    --no-fail-on-empty-changeset

echo "  ✓ CloudFormation stack deployed/updated"
echo ""

# ---------------------------
# Cleanup
# ---------------------------
rm -rf "${BUILD_DIR}"

echo "============================================="
echo " Deployment complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo "  1. Check CloudWatch Logs for the MetricCollector Lambda execution"
echo "  2. Verify data in Aurora PostgreSQL cloudwatch_metrics table"
echo "  3. Confirm EventBridge rule is triggering every 5 minutes"
echo ""
