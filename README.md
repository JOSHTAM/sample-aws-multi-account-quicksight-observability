# Multi-Account QuickSight Observability

[![AWS](https://img.shields.io/badge/AWS-Lambda-orange.svg)](https://aws.amazon.com/lambda/)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![CloudFormation](https://img.shields.io/badge/CloudFormation-Template-green.svg)](https://aws.amazon.com/cloudformation/)
[![Aurora](https://img.shields.io/badge/Aurora-PostgreSQL-purple.svg)](https://aws.amazon.com/rds/aurora/)
[![License](https://img.shields.io/badge/License-MIT--0-blue.svg)](LICENSE)

A comprehensive AWS multi-account observability solution built on a hub-spoke architecture. It centralizes operational, security, compliance, and cost data from many AWS accounts into a single Aurora PostgreSQL database and surfaces it through a ready-to-import **Amazon QuickSight executive dashboard**.

Beyond daily inventory collection, this version adds an **executive observability layer**: near-real-time CloudWatch metric collection across accounts (via CloudWatch cross-account observability / OAM), consolidated CloudWatch alarm and synthetic-canary health, composite per-system health scoring, and an optional alerting path for critical issues. The dashboard ships pre-built so a fresh deployment reproduces the same layout and visuals — populated entirely by *your* accounts' real data, with no sample or synthetic data included.

## Table of Contents

- [What's New in This Version](#whats-new-in-this-version)
- [Architecture](#architecture)
- [Features](#features)
- [Cost](#cost)
- [Prerequisites](#prerequisites)
- [Regions](#regions)
- [Getting Started](#getting-started)
- [Repository Layout](#repository-layout)
- [Security](#security)
- [License](#license)
- [Credits](#credits)
- [Support](#support)

## What's New in This Version

This solution extends a plain multi-account data collector into an executive-focused observability platform. The additions are:

| Capability | What it does | Where |
|-----------|--------------|-------|
| **QuickSight executive dashboard** | A pre-built analysis with an **Overview** sheet (per-system health scores, availability, alarms, warnings, account summary) plus per-**System** drill-down sheets. Ships as an importable QuickSight asset bundle. | `quicksuite/`, `quicksight/` |
| **Near-real-time metric collection** | A Metric Collector Lambda pulls CloudWatch metrics from all linked accounts every 5 minutes using CloudWatch cross-account observability (OAM) and stores them in a weekly-partitioned table. | `scripts/metric_collector.py` |
| **Consolidated alarm & canary health** | CloudWatch alarm states and CloudWatch Synthetics canary results are collected and modeled, feeding availability and health visuals. | `scripts/metric_collector.py`, `scripts/receiver.py`, schema tables `alarms`, `alarm_states`, `canaries`, `canary_runs` |
| **Composite health scoring** | Each system gets a health score derived from alarm status, security findings, resource availability, and performance. | `sql/schema/core-view.sql`, `scripts/dashboard_helpers.py` |
| **Executive alert processing** | An Alert Processor Lambda classifies alarm severity, detects consecutive canary failures, and (optionally) forwards Critical/High alerts to a Slack incoming webhook with rate limiting. Cross-account alarm state changes are forwarded to the hub over a dedicated EventBridge bus. **Disabled by default** — no webhook is configured unless you set one. | `scripts/alert_processor.py`, `executive-alerts-bus` |
| **Automated data retention** | A daily Data Retention Lambda prunes real-time metric/alarm rows older than a configurable window (default 90 days). | `scripts/data_retention.py` |
| **New-system onboarding workflow** | A documented, repeatable flow to add a new source account and give it its own dashboard sheet. | [docs/onboarding-a-new-system.md](docs/onboarding-a-new-system.md) |

> This repository is **standalone** — everything you need to deploy is included. You do not need any other repository.

## Architecture

> **📋 NOTE:** For detailed step-by-step instructions, see the [Deployment Guide](docs/deployment-guide.md). An editable architecture diagram is included at [`docs/multi-account-observability-architecture.drawio`](docs/multi-account-observability-architecture.drawio).

This hub-spoke architecture enables centralized multi-account observability with flexible processing options and comprehensive security controls.

**Hub (Analytics Account)**: Central aggregation point that receives, processes, and stores data from all source accounts. Contains the Aurora PostgreSQL database, the receiver/metric-collector/alert-processor/retention Lambdas, the EventBridge schedules and alert bus, and the QuickSight dashboard.

**Spokes (Source Accounts)**: Distributed AWS accounts that publish data. Each runs a lightweight sender Lambda that collects 15+ data categories (plus alarms and canaries) and publishes an encrypted payload to the hub, and forwards CloudWatch alarm state changes to the hub's alert bus.

### Data Flow

**Daily inventory path**

| Step | Process | Location |
|------|---------|----------|
| 1 | EventBridge daily schedule triggers the Sender Lambda | Source Account |
| 2 | Sender collects 15+ categories + alarms + canaries and uploads a KMS-encrypted JSON to `data/` | Hub S3 |
| 3 | S3 `ObjectCreated` event triggers the Receiver (Lambda, or EC2 in Option B) | Hub |
| 4 | Receiver upserts the data into Aurora PostgreSQL | Hub VPC |
| 5 | QuickSight reads the Aurora views over a VPC connection | Hub |

**Near-real-time path**

| Step | Process | Location |
|------|---------|----------|
| A | EventBridge (every 5 min) triggers the Metric Collector, which reads CloudWatch metrics/alarms from all linked accounts via OAM and writes `cloudwatch_metrics` / `alarm_states` | Hub |
| B | Source-account CloudWatch "Alarm State Change" events are forwarded to the hub's `executive-alerts-bus`, invoking the Alert Processor (severity classification, optional Slack) | Source → Hub |
| C | A daily Data Retention Lambda prunes real-time rows older than the retention window | Hub |

> **Where does each dashboard number come from?** For a complete, per-dataset trace —
> AWS source API → collector Lambda → Aurora table → SQL view → QuickSight dataset →
> visual — see the [Data Lineage guide](docs/data-lineage.md).

## Features

- **Multi-Account Collection**: Aggregates data from multiple AWS accounts and regions across 15+ categories including AWS Cost Explorer, AWS Security Hub, Amazon GuardDuty, Amazon Inspector, AWS Config, AWS Systems Manager, AWS WAF, ACM, KMS, Secrets Manager, and (with a Business/Enterprise support plan) AWS Support / Trusted Advisor / Health.
- **Near-Real-Time Metrics**: CloudWatch metrics and alarm states collected every 5 minutes across all linked accounts via CloudWatch cross-account observability (OAM), stored in a weekly-partitioned time-series table.
- **Executive Dashboard**: A pre-built QuickSight analysis with an Overview sheet and per-System drill-downs, including composite health scores and synthetic-canary availability.
- **Optional Alerting**: Severity-classified, rate-limited Slack notifications for Critical/High alarms, P1/P2 incidents, and repeatedly-failing canaries — off unless a webhook is configured.
- **Flexible Processing**: Choose serverless Lambda for auto-scaling (Option A) or an EC2 receiver for large payloads / compliance requirements (Option B), selected by a single CloudFormation parameter.
- **Ready-to-Use Data Model**: 45+ tables and 45+ pre-built views feeding the dashboard, with zero sample data — tables start empty and fill from your real accounts.

### Data Categories

The Sender automatically collects data across 15+ AWS service categories from each source account.

| Category | AWS Service | Data Collected |
|----------|-------------|----------------|
| **Cost** | AWS Cost Explorer | Daily costs, forecasts, usage reports |
| **Security** | AWS Security Hub, Amazon GuardDuty, Amazon Inspector, AWS CloudTrail | Security findings, compliance status, threat detection, vulnerability assessments, API audit logs |
| **Configuration** | AWS Config | Resource compliance, configuration changes |
| **Inventory** | AWS Systems Manager | EC2 instances, patch compliance, inventory |
| **Support** | AWS Support API | Support cases, Trusted Advisor recommendations |
| **Trusted Advisor** | AWS Trusted Advisor | Recommendations and best practices |
| **Health** | AWS Health API | Service health events, maintenance notifications |
| **Web Security** | AWS WAF | Web application firewall rules |
| **Certificates** | AWS Certificate Manager | SSL/TLS certificates, expiration dates |
| **Encryption** | AWS KMS | Key usage, encryption status |
| **Secrets** | AWS Secrets Manager | Secret rotation, access patterns |
| **Availability** | CloudWatch Alarms & Synthetics | Alarm states, canary pass/fail, per-system health |
| **Metrics** | CloudWatch (via OAM) | Near-real-time metric time series |

## Cost

Comprehensive monthly/annual cost estimates for the analytics (hub) account infrastructure. Costs are based on moderate usage and vary with data volume, number of connected accounts, query frequency, user activity, region, and configuration.

| Service | Option A (Serverless) | Option B (EC2) | Comments |
|---------|----------------------|----------------|---------------|
| Aurora PostgreSQL | $156.64 | $156.64 | Same database required for both options |
| Lambda Functions | $68 | $0.13 | Serverless uses Lambda for the receiver; EC2 option offloads it |
| EC2 Instance | $0 | $3.80 | EC2 option uses a t4g.small instance for processing |
| S3 Storage | $0.67 | $0.67 | Same storage requirements for both options |
| QuickSight | $141 | $141 | Same dashboard and user licensing costs |
| KMS | $7 | $7 | Same encryption requirements |
| VPC/Networking | $28 | $114 | EC2 option adds interface VPC endpoints |
| Other Services | $0.41 | $0.41 | SQS, Secrets Manager, EventBridge, etc. |
| **TOTAL/MONTH** | **~$402.57** | **~$423.58** |  |
| **TOTAL/YEAR** | **~$4,830** | **~$5,082** | The EC2 option costs more due to the instance and VPC endpoints but has predictable fixed costs; the serverless option's cost varies with Lambda execution time and data volume. |

> **⚠️ DISCLAIMER**
>
> Cost estimates are informational only (AWS pricing as of January 2025, US East region) and exclude the near-real-time Metric Collector's incremental Lambda/CloudWatch cost, which depends on the number of accounts and metrics collected. Actual costs vary by usage, region, and configuration.
>
> **Recommendation**: Use the [AWS Pricing Calculator](https://calculator.aws) for official estimates and monitor with AWS Cost Explorer.
>
> *Estimates do not constitute a quote or commitment.*

## Prerequisites

You need access to an AWS account for the hub. We recommend a dedicated Data Collection / Analytics account, separate from your Management (payer) account. CloudFormation templates are provided for the hub and for each source account.

- **Amazon QuickSight / Quick Suite (Enterprise)** enabled in the hub account, in the same region as the hub.
- **CloudWatch cross-account observability (OAM)** configured so the hub is a monitoring account linked to your source accounts — required for the near-real-time Metric Collector.

### AWS Services

| Required Services | Optional Services |
|-------------------|-------------------|
| AWS Security Token Service (STS) | Amazon Relational Database Service (RDS) |
| AWS Account Management | Amazon Simple Storage Service (S3) |
| AWS Cost Explorer | Elastic Load Balancing v2 |
| AWS Security Hub | AWS Resilience Hub |
| AWS Config | AWS Compute Optimizer |
| AWS Identity and Access Management (IAM) | AWS Support* |
| Amazon Elastic Compute Cloud (EC2) | AWS Trusted Advisor* |
| Amazon CloudWatch (Metrics, Alarms, Synthetics, OAM) | AWS Health* |
| AWS Systems Manager | |
| Amazon Inspector | |
| AWS Web Application Firewall (WAF) v2 | |

*Access requires a Business or Enterprise support plan. Without it, Health, Trusted Advisor, and Support ticket collection are unavailable.

## Regions

Install data collection in the same region where you consume the data to avoid cross-region charges. A source account used in multiple regions needs the Sender template deployed in each region.

## Getting Started

The deployment sets up the central analytics hub, loads the database, provisions the QuickSight dashboard, and connects your source accounts. Full details are in the [Deployment Guide](docs/deployment-guide.md); this is the high-level sequence.

> **ℹ️ Note:** For the full near-real-time dashboard feature set, deploy `cloudformation/A360-Analytics.yaml`. The `A360-Analytics-Custom-VPC.yaml` variant deploys into an existing VPC but includes only the core collector (no Metric Collector / Alert Processor / retention).

| Step | Description |
|------|-------------|
| **1. Clone this repository** | `git clone https://github.com/JOSHTAM/sample-aws-multi-account-quicksight-observability.git` |
| **2. Deploy the Analytics hub** | Deploy `cloudformation/A360-Analytics.yaml`.<br>**Option A (Serverless)**: set *Deploy EC2 Receiver = No* (Lambda receiver).<br>**Option B (EC2)**: set *Deploy EC2 Receiver = Yes* for large payloads / compliance. |
| **3. Upload assets to S3** | Upload the `scripts/` and `quicksuite/` folders and `config/metric_definitions.json` + `config/exclude.json` to the hub's `-data` bucket. All Lambdas load their code from `scripts/` at runtime — no packaging needed. |
| **4. Wire triggers** | Add the S3 `ObjectCreated` trigger to the Receiver Lambda (the 5-minute metric-collection and daily retention schedules are created by the template). |
| **5. Set up the database** | In the Aurora Query Editor (database `core`), run `sql/schema/core-schema.sql`, then `sql/schema/core-view.sql`, then `sql/schema/partitions.sql` (required for the real-time metrics table). |
| **6. Configure QuickSight** | Enable Enterprise edition, create the VPC connection, and create an Aurora data source (database `core`). |
| **7. Import the dashboard** | Deploy `cloudformation/A360-QS-Migration.yaml` and run its Lambda's **Test** action to import the analysis from `quicksuite/A360-Sample-Template.qs` and point its datasets at your Aurora data source. See [quicksight/README.md](quicksight/README.md). |
| **8. Deploy source accounts** | Deploy `cloudformation/A360-Sender.yaml` in each source account, pointing it at the hub's account ID, S3 bucket, and KMS key. |
| **9. Onboard systems** | Register each product/system and give it a dashboard sheet — see [Onboarding a New System](docs/onboarding-a-new-system.md). |

## Repository Layout

```
cloudformation/   Hub, sender, and QuickSight-migration templates
scripts/          Sender, receiver, metric collector, alert processor, retention, helpers + config
sql/              Aurora schema, views, weekly partitions, and helper queries
quicksuite/       Importable QuickSight dashboard bundle (.qs) used by the migration Lambda
quicksight/       QuickSight dashboard assets (CFN asset bundle + analysis definition) and guide
docs/             Deployment guides, onboarding guide, architecture diagram, data format, roadmap
migrations/       Version-to-version migration notes
```

## Security

When you build on AWS, security responsibilities are shared between you and AWS. AWS operates, manages, and controls the host operating system, virtualization layer, and physical facility security. For more information, see [AWS Cloud Security](https://aws.amazon.com/security/).

This solution encrypts data at rest with KMS, denies non-TLS access to the S3 bucket, uses Secrets Manager for database credentials, and scopes cross-account access to the specific sender accounts you list. Review IAM policies and network configuration against your organization's requirements before production use.

See [CONTRIBUTING](CONTRIBUTING.md) for more information.

## License

This project is licensed under the **MIT No Attribution (MIT-0)** license — see the [LICENSE](LICENSE) file. MIT-0 permits use, modification, and distribution for any purpose without requiring attribution.

## Credits

This solution builds on the open-source [AWS Samples multi-account observability project](https://github.com/aws-samples/sample-aws-multi-account-observability) (MIT-0), extending it with the executive QuickSight dashboard, near-real-time cross-account metric collection, alarm/canary health, health scoring, and the onboarding workflow described above. You do **not** need that project to deploy this one — this repository is fully standalone.

## Support

### Getting Help
- **Documentation**: See the [Deployment Guide](docs/deployment-guide.md)
- **Issues**: Report bugs and request features via [GitHub Issues](../../issues)
- **Troubleshooting**: Review CloudWatch logs and verify IAM permissions

### Resources
- 📖 [Detailed Deployment Guide](docs/deployment-guide.md)
- 🖥️ [QuickSight Dashboard Assets](quicksight/README.md)
- 🔗 [Data Lineage (source → table → dataset → visual)](docs/data-lineage.md)
- 📈 [Health Score & Overview Metrics](docs/quicksight/health-scoring.md)
- ➕ [Onboarding a New System](docs/onboarding-a-new-system.md)
- 🗺️ [Roadmap / Future Scope](docs/ROADMAP.md)
- 🔧 [AWS API Documentation](docs/aws-api-documentation.md)
- 🔄 [Migration Guide](migrations/00-v1.x-to-v2.x-migration/migration-guide.md)
- 📊 [SQL Helper Guide](sql/a360-sql-helper.md)
- `{}` [Data Format](docs/data_format.md)
