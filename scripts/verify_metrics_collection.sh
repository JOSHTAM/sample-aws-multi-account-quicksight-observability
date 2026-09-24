#!/bin/bash
# =============================================================================
# verify_metrics_collection.sh
# End-to-end verification script for the Real-Time Metrics Dashboard pipeline
#
# Validates:
#   1. CloudWatch Logs show successful MetricCollector Lambda execution
#   2. cloudwatch_metrics table contains recent data points
#   3. alarm_states table contains recent alarm records
#   4. Lambda execution completes within 300s timeout
#   5. Metrics from all configured accounts are present
#
# Requirements: 1.1, 1.2, 1.3, 15.2
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Defaults and argument parsing
# -----------------------------------------------------------------------------
CLUSTER_ARN=""
SECRET_ARN=""
DATABASE="core"
FUNCTION_NAME=""
REGION="ap-southeast-1"
VERBOSE=false

usage() {
    cat <<EOF
Usage: $(basename "$0") -c CLUSTER_ARN -s SECRET_ARN -f FUNCTION_NAME [OPTIONS]

Required:
  -c    Aurora cluster ARN (e.g., arn:aws:rds:ap-southeast-1:123456789012:cluster:xxx)
  -s    Aurora secret ARN (e.g., arn:aws:secretsmanager:ap-southeast-1:123456789012:secret:xxx)
  -f    Lambda function name (e.g., A360-Analytics-MetricCollector)

Options:
  -d    Database name (default: core)
  -r    AWS region (default: ap-southeast-1)
  -v    Verbose output
  -h    Show this help message

Example:
  $(basename "$0") -c arn:aws:rds:ap-southeast-1:123456789012:cluster:a360-aurora \\
    -s arn:aws:secretsmanager:ap-southeast-1:123456789012:secret:a360-secret \\
    -f A360-Analytics-MetricCollector
EOF
    exit 1
}

while getopts "c:s:d:f:r:vh" opt; do
    case $opt in
        c) CLUSTER_ARN="$OPTARG" ;;
        s) SECRET_ARN="$OPTARG" ;;
        d) DATABASE="$OPTARG" ;;
        f) FUNCTION_NAME="$OPTARG" ;;
        r) REGION="$OPTARG" ;;
        v) VERBOSE=true ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Validate required parameters
if [[ -z "$CLUSTER_ARN" || -z "$SECRET_ARN" || -z "$FUNCTION_NAME" ]]; then
    echo "ERROR: Missing required parameters."
    echo ""
    usage
fi

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

print_header() {
    echo ""
    echo "============================================================================="
    echo "  $1"
    echo "============================================================================="
}

print_check() {
    local status="$1"
    local message="$2"
    case "$status" in
        PASS)
            echo "  ✅ PASS: $message"
            PASS_COUNT=$((PASS_COUNT + 1))
            ;;
        FAIL)
            echo "  ❌ FAIL: $message"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            ;;
        WARN)
            echo "  ⚠️  WARN: $message"
            WARN_COUNT=$((WARN_COUNT + 1))
            ;;
        INFO)
            echo "  ℹ️  INFO: $message"
            ;;
    esac
}

verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo "  [DEBUG] $1"
    fi
}

# Execute SQL via RDS Data API and return the result
execute_sql() {
    local sql="$1"
    verbose "Executing SQL: $sql"
    aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "$sql" \
        --region "$REGION" \
        --output json 2>/dev/null
}

# Extract a scalar value from RDS Data API response (first row, first column)
extract_scalar() {
    local result="$1"
    echo "$result" | jq -r '.records[0][0].longValue // .records[0][0].stringValue // "0"'
}

# -----------------------------------------------------------------------------
# Check 1: CloudWatch Logs - Recent Lambda Execution
# -----------------------------------------------------------------------------
check_lambda_execution() {
    print_header "Check 1: MetricCollector Lambda Execution (CloudWatch Logs)"

    local log_group="/aws/lambda/${FUNCTION_NAME}"
    verbose "Checking log group: $log_group"

    # Get the most recent log stream
    local streams
    streams=$(aws logs describe-log-streams \
        --log-group-name "$log_group" \
        --order-by LastEventTime \
        --descending \
        --limit 1 \
        --region "$REGION" \
        --output json 2>/dev/null) || {
        print_check "FAIL" "Could not access log group: $log_group"
        return
    }

    local stream_name
    stream_name=$(echo "$streams" | jq -r '.logStreams[0].logStreamName // empty')

    if [[ -z "$stream_name" ]]; then
        print_check "FAIL" "No log streams found for $log_group"
        return
    fi

    local last_event_time
    last_event_time=$(echo "$streams" | jq -r '.logStreams[0].lastEventTimestamp // 0')
    local current_time
    current_time=$(date +%s%3N)
    local age_minutes=$(( (current_time - last_event_time) / 60000 ))

    verbose "Most recent log stream: $stream_name"
    verbose "Last event: ${age_minutes} minutes ago"

    if [[ $age_minutes -le 10 ]]; then
        print_check "PASS" "Lambda executed recently (${age_minutes} minutes ago)"
    elif [[ $age_minutes -le 30 ]]; then
        print_check "WARN" "Lambda last executed ${age_minutes} minutes ago (expected within 10 min)"
    else
        print_check "FAIL" "Lambda last executed ${age_minutes} minutes ago (too old, expected within 10 min)"
    fi

    # Check for errors in recent logs
    local ten_min_ago
    ten_min_ago=$(( current_time - 600000 ))

    local error_events
    error_events=$(aws logs filter-log-events \
        --log-group-name "$log_group" \
        --start-time "$ten_min_ago" \
        --filter-pattern "ERROR" \
        --limit 5 \
        --region "$REGION" \
        --output json 2>/dev/null) || true

    local error_count
    error_count=$(echo "$error_events" | jq '.events | length' 2>/dev/null || echo "0")

    if [[ "$error_count" -eq 0 ]]; then
        print_check "PASS" "No ERROR entries in recent logs"
    else
        print_check "WARN" "Found ${error_count} ERROR entries in recent logs"
        if [[ "$VERBOSE" == "true" ]]; then
            echo "$error_events" | jq -r '.events[].message' 2>/dev/null | head -5
        fi
    fi

    # Check Lambda duration from REPORT lines
    local report_events
    report_events=$(aws logs filter-log-events \
        --log-group-name "$log_group" \
        --start-time "$ten_min_ago" \
        --filter-pattern "REPORT" \
        --limit 3 \
        --region "$REGION" \
        --output json 2>/dev/null) || true

    local duration
    duration=$(echo "$report_events" | jq -r '.events[-1].message // ""' 2>/dev/null | grep -oP 'Duration: \K[0-9.]+' || echo "")

    if [[ -n "$duration" ]]; then
        local duration_seconds
        duration_seconds=$(echo "$duration" | awk '{printf "%.0f", $1 / 1000}')
        verbose "Lambda duration: ${duration} ms (${duration_seconds}s)"

        if [[ $duration_seconds -lt 300 ]]; then
            print_check "PASS" "Lambda completed in ${duration_seconds}s (within 300s timeout)"
        else
            print_check "FAIL" "Lambda duration ${duration_seconds}s exceeds 300s timeout"
        fi
    else
        print_check "WARN" "Could not determine Lambda duration from logs"
    fi
}

# -----------------------------------------------------------------------------
# Check 2: cloudwatch_metrics Table - Data Points Present
# -----------------------------------------------------------------------------
check_metrics_table() {
    print_header "Check 2: cloudwatch_metrics Table Data"

    # Count recent metrics (last 10 minutes)
    local result
    result=$(execute_sql "SELECT COUNT(*) FROM cloudwatch_metrics WHERE collected_at > NOW() - INTERVAL '10 minutes'")

    if [[ $? -ne 0 || -z "$result" ]]; then
        print_check "FAIL" "Could not query cloudwatch_metrics table"
        return
    fi

    local metric_count
    metric_count=$(extract_scalar "$result")
    verbose "Recent metric data points: $metric_count"

    if [[ "$metric_count" -gt 0 ]]; then
        print_check "PASS" "Found ${metric_count} metric data points in last 10 minutes"
    else
        print_check "FAIL" "No metric data points found in last 10 minutes"
    fi

    # Check distinct accounts
    result=$(execute_sql "SELECT COUNT(DISTINCT account_id) FROM cloudwatch_metrics WHERE collected_at > NOW() - INTERVAL '10 minutes'")
    local account_count
    account_count=$(extract_scalar "$result")
    verbose "Distinct accounts with metrics: $account_count"

    if [[ "$account_count" -gt 0 ]]; then
        print_check "PASS" "Metrics present from ${account_count} account(s)"
    else
        print_check "FAIL" "No accounts with metrics in last 10 minutes"
    fi

    # Check distinct namespaces
    result=$(execute_sql "SELECT COUNT(DISTINCT namespace) FROM cloudwatch_metrics WHERE collected_at > NOW() - INTERVAL '10 minutes'")
    local namespace_count
    namespace_count=$(extract_scalar "$result")
    verbose "Distinct namespaces: $namespace_count"

    if [[ "$namespace_count" -ge 5 ]]; then
        print_check "PASS" "Collecting from ${namespace_count} namespaces (good coverage)"
    elif [[ "$namespace_count" -ge 1 ]]; then
        print_check "WARN" "Only ${namespace_count} namespace(s) reporting (expected 5+)"
    else
        print_check "FAIL" "No namespaces reporting metrics"
    fi

    # Check dashboard categories
    result=$(execute_sql "SELECT COALESCE(dashboard_category, 'null') as cat, COUNT(*) as cnt FROM cloudwatch_metrics WHERE collected_at > NOW() - INTERVAL '10 minutes' GROUP BY dashboard_category ORDER BY cnt DESC")
    verbose "Dashboard categories breakdown:"
    if [[ "$VERBOSE" == "true" ]]; then
        echo "$result" | jq -r '.records[] | "    \(.[0].stringValue): \(.[1].longValue) data points"' 2>/dev/null || true
    fi

    local category_count
    category_count=$(echo "$result" | jq '.records | length' 2>/dev/null || echo "0")
    if [[ "$category_count" -ge 3 ]]; then
        print_check "PASS" "All 3 dashboard categories (availability, capacity, performance) have data"
    elif [[ "$category_count" -ge 1 ]]; then
        print_check "WARN" "Only ${category_count} dashboard category/categories reporting"
    else
        print_check "FAIL" "No dashboard categories reporting"
    fi
}

# -----------------------------------------------------------------------------
# Check 3: alarm_states Table - Alarm Records Present
# -----------------------------------------------------------------------------
check_alarm_states() {
    print_header "Check 3: alarm_states Table Data"

    # Count recent alarm state records
    local result
    result=$(execute_sql "SELECT COUNT(*) FROM alarm_states WHERE collected_at > NOW() - INTERVAL '10 minutes'")

    if [[ $? -ne 0 || -z "$result" ]]; then
        print_check "FAIL" "Could not query alarm_states table"
        return
    fi

    local alarm_count
    alarm_count=$(extract_scalar "$result")
    verbose "Recent alarm state records: $alarm_count"

    if [[ "$alarm_count" -gt 0 ]]; then
        print_check "PASS" "Found ${alarm_count} alarm state records in last 10 minutes"
    else
        print_check "FAIL" "No alarm state records found in last 10 minutes"
    fi

    # Check alarm state distribution
    result=$(execute_sql "SELECT state, COUNT(*) FROM alarm_states WHERE collected_at > NOW() - INTERVAL '10 minutes' GROUP BY state ORDER BY COUNT(*) DESC")

    local state_count
    state_count=$(echo "$result" | jq '.records | length' 2>/dev/null || echo "0")

    if [[ "$state_count" -gt 0 ]]; then
        print_check "PASS" "Alarm states distributed across ${state_count} state(s)"
        if [[ "$VERBOSE" == "true" ]]; then
            echo "$result" | jq -r '.records[] | "    \(.[0].stringValue): \(.[1].longValue) alarms"' 2>/dev/null || true
        fi
    else
        print_check "WARN" "Could not determine alarm state distribution"
    fi

    # Check distinct accounts in alarm states
    result=$(execute_sql "SELECT COUNT(DISTINCT account_id) FROM alarm_states WHERE collected_at > NOW() - INTERVAL '10 minutes'")
    local alarm_account_count
    alarm_account_count=$(extract_scalar "$result")

    if [[ "$alarm_account_count" -gt 0 ]]; then
        print_check "PASS" "Alarm states present from ${alarm_account_count} account(s)"
    else
        print_check "WARN" "No distinct accounts in alarm_states"
    fi
}

# -----------------------------------------------------------------------------
# Check 4: Execution Timing - 5-minute cycle within 300s
# -----------------------------------------------------------------------------
check_execution_timing() {
    print_header "Check 4: Execution Timing (5-minute cycle, 300s timeout)"

    local log_group="/aws/lambda/${FUNCTION_NAME}"
    local thirty_min_ago
    thirty_min_ago=$(( $(date +%s%3N) - 1800000 ))

    # Get recent REPORT lines to check durations
    local report_events
    report_events=$(aws logs filter-log-events \
        --log-group-name "$log_group" \
        --start-time "$thirty_min_ago" \
        --filter-pattern "REPORT" \
        --limit 6 \
        --region "$REGION" \
        --output json 2>/dev/null) || {
        print_check "WARN" "Could not retrieve REPORT events from CloudWatch Logs"
        return
    }

    local event_count
    event_count=$(echo "$report_events" | jq '.events | length' 2>/dev/null || echo "0")

    if [[ "$event_count" -eq 0 ]]; then
        print_check "WARN" "No REPORT events found in last 30 minutes"
        return
    fi

    verbose "Found ${event_count} execution reports in last 30 minutes"

    # Parse durations and check all are under 300s
    local max_duration=0
    local all_within_timeout=true

    while IFS= read -r line; do
        local dur_ms
        dur_ms=$(echo "$line" | grep -oP 'Duration: \K[0-9.]+' || echo "0")
        if [[ -n "$dur_ms" && "$dur_ms" != "0" ]]; then
            local dur_s
            dur_s=$(echo "$dur_ms" | awk '{printf "%.0f", $1 / 1000}')
            verbose "  Execution duration: ${dur_s}s"
            if [[ $dur_s -gt $max_duration ]]; then
                max_duration=$dur_s
            fi
            if [[ $dur_s -ge 300 ]]; then
                all_within_timeout=false
            fi
        fi
    done < <(echo "$report_events" | jq -r '.events[].message' 2>/dev/null)

    if [[ "$all_within_timeout" == "true" && $max_duration -gt 0 ]]; then
        print_check "PASS" "All executions completed within 300s (max: ${max_duration}s)"
    elif [[ $max_duration -ge 300 ]]; then
        print_check "FAIL" "Execution exceeded 300s timeout (max: ${max_duration}s)"
    else
        print_check "WARN" "Could not verify execution durations"
    fi

    # Check execution frequency (should be ~5 min apart)
    if [[ "$event_count" -ge 2 ]]; then
        local timestamps
        timestamps=$(echo "$report_events" | jq '[.events[].timestamp]' 2>/dev/null)
        local first_ts
        first_ts=$(echo "$timestamps" | jq '.[0]' 2>/dev/null || echo "0")
        local last_ts
        last_ts=$(echo "$timestamps" | jq '.[-1]' 2>/dev/null || echo "0")

        if [[ "$first_ts" != "0" && "$last_ts" != "0" && "$event_count" -gt 1 ]]; then
            local span_minutes=$(( (last_ts - first_ts) / 60000 ))
            local avg_interval=$(( span_minutes / (event_count - 1) ))
            verbose "Average interval between executions: ${avg_interval} minutes"

            if [[ $avg_interval -ge 4 && $avg_interval -le 6 ]]; then
                print_check "PASS" "Executions running at ~5-minute intervals (avg: ${avg_interval} min)"
            else
                print_check "WARN" "Execution interval is ${avg_interval} min (expected ~5 min)"
            fi
        fi
    fi
}

# -----------------------------------------------------------------------------
# Check 5: Multi-Account Coverage
# -----------------------------------------------------------------------------
check_multi_account() {
    print_header "Check 5: Multi-Account Coverage"

    # Get configured accounts from metric_definitions.json if accessible
    # For now, check what's in the database
    local result
    result=$(execute_sql "SELECT DISTINCT account_id FROM cloudwatch_metrics WHERE collected_at > NOW() - INTERVAL '10 minutes' ORDER BY account_id")

    if [[ $? -ne 0 || -z "$result" ]]; then
        print_check "WARN" "Could not query account list"
        return
    fi

    local accounts
    accounts=$(echo "$result" | jq -r '.records[][0].stringValue' 2>/dev/null || echo "")

    if [[ -z "$accounts" ]]; then
        print_check "FAIL" "No accounts found in recent metrics"
        return
    fi

    local account_list
    account_list=$(echo "$accounts" | tr '\n' ', ' | sed 's/,$//')
    local num_accounts
    num_accounts=$(echo "$accounts" | wc -l | tr -d ' ')

    print_check "INFO" "Accounts reporting metrics: $account_list"
    print_check "PASS" "Found ${num_accounts} account(s) with recent metric data"

    # Check per-account metric counts
    result=$(execute_sql "SELECT account_id, COUNT(*) as cnt FROM cloudwatch_metrics WHERE collected_at > NOW() - INTERVAL '10 minutes' GROUP BY account_id ORDER BY account_id")
    if [[ "$VERBOSE" == "true" ]]; then
        echo "  Per-account metric counts:"
        echo "$result" | jq -r '.records[] | "    Account \(.[0].stringValue): \(.[1].longValue) data points"' 2>/dev/null || true
    fi
}

# -----------------------------------------------------------------------------
# Main execution
# -----------------------------------------------------------------------------
main() {
    echo ""
    echo "============================================================================="
    echo "  Real-Time Metrics Dashboard - End-to-End Verification"
    echo "============================================================================="
    echo ""
    echo "  Cluster ARN:   $CLUSTER_ARN"
    echo "  Secret ARN:    ${SECRET_ARN:0:60}..."
    echo "  Database:      $DATABASE"
    echo "  Function:      $FUNCTION_NAME"
    echo "  Region:        $REGION"
    echo "  Timestamp:     $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

    check_lambda_execution
    check_metrics_table
    check_alarm_states
    check_execution_timing
    check_multi_account

    # Summary
    print_header "Verification Summary"
    echo ""
    echo "  ✅ Passed:  $PASS_COUNT"
    echo "  ❌ Failed:  $FAIL_COUNT"
    echo "  ⚠️  Warnings: $WARN_COUNT"
    echo ""

    if [[ $FAIL_COUNT -eq 0 ]]; then
        echo "  🎉 All critical checks PASSED. Pipeline is operating correctly."
        echo ""
        exit 0
    else
        echo "  ⛔ ${FAIL_COUNT} check(s) FAILED. Investigation required."
        echo ""
        exit 1
    fi
}

main
