# QuickSight Dashboard Assets

This folder contains an exported, ready-to-import copy of the **View 360 Observability
Dashboard** so that a fresh deployment reproduces the exact same dashboard — layout,
calculated fields, filters, and conditional formatting — that ships with this solution.

The dashboard has two sheets out of the box:

| Sheet | Purpose |
|-------|---------|
| **Overview** | Cross-system health scores, availability, alarms, warnings, and account summary for every monitored system. **How every tile is calculated — and how to reconfigure the score, bands, colours, and icons — is documented in [docs/quicksight/health-scoring.md](../docs/quicksight/health-scoring.md).** |
| **System A** | Per-system drill-down: critical/high/medium alarms, alarm frequency, active alarms table, and synthetic-canary availability. This is also the **template** you duplicate when onboarding additional systems (see the onboarding guide). |

> The Overview ships with 6 placeholder system slots (**System A … System F**) and one
> detail sheet (**System A**). The system **names** and the per-visual **filters** are
> placeholders you point at your real systems — see
> [what auto-populates vs. what you configure](../docs/onboarding-a-new-system.md#what-auto-populates-vs-what-you-configure-by-hand).

> The dashboard is data-driven. On a fresh deployment every table is empty, so the
> dashboard renders zeros/blank until your sender and collector Lambdas begin writing
> your own accounts' real data. **No sample or synthetic data is shipped.** A system
> with nothing wrong (or nothing yet collected) shows a health score of **100
> (Healthy)** — the score only drops when real problems are observed. See
> [docs/quicksight/health-scoring.md](../docs/quicksight/health-scoring.md) for the
> full scoring model and self-serve configuration guide.

## Files

| File | What it is |
|------|-----------|
| `../quicksuite/A360-Sample-Template.qs` | The QuickSight asset bundle (analysis + 20 datasets + data source + VPC connection) in QuickSight-JSON (`.qs`) format. This is what the `A360-QS-Migration.yaml` migration Lambda imports. **This is the primary, supported provisioning path** and matches the documented deployment steps. |
| `quicksight-dashboard.template.json` | The same assets exported as a **CloudFormation** template (QuickSight asset-bundle format). Provided as an infrastructure-as-code alternative for teams that prefer to provision the dashboard via a CloudFormation stack. |
| `analysis-definition.json` | The raw analysis definition (all visuals, sheets, calculated fields, filters). Reference material for customizing the dashboard or rebuilding sheets by hand. |

All three are genericized: no real account IDs, no real ARNs, no customer/agency names.
Placeholder values you must replace are written as `REPLACE_WITH_YOUR_...`,
`111111111111` / `222222222222` (source / hub account), or `123456789012`.

## Provisioning options

### Option 1 (recommended) — migration Lambda + `.qs`

This is the path described in the main
[deployment guide](../docs/option-a-serverless-deployment.md#step-7-migrate-analysis).
In short:

1. Deploy the analytics hub (`cloudformation/A360-Analytics.yaml`).
2. Upload the `quicksuite/` and `scripts/` folders to the analytics S3 bucket.
3. Create a QuickSight data source pointing at your Aurora cluster (database `core`).
4. Deploy `cloudformation/A360-QS-Migration.yaml`, pointing `S3Uri` at
   `s3://<your-bucket>/quicksuite/A360-Sample-Template.qs`.
5. Run the migration Lambda's **Test** action. It imports the analysis and re-points every
   dataset at your own Aurora data source.

### Option 2 — CloudFormation asset bundle

If you prefer pure IaC, deploy `quicksight-dashboard.template.json` as a CloudFormation
stack. Provide your own values for the parameters (VPC connection subnets, security group,
and Aurora secret ARN) — these ship without defaults on purpose.

## Adding a sheet for a new system

When you onboard a new source account/system, point its **Overview card** (rename the
title, re-point each tile's `system_name` filter) and duplicate the **System A** sheet for
its detail view, re-pointing the filters. Full step-by-step instructions — including which
parts auto-populate and which are manual placeholders — are in the
[onboarding guide](../docs/onboarding-a-new-system.md).
