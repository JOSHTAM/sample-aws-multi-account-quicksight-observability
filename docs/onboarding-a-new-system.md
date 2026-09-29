# Onboarding a New System (Source Account)

This guide explains how to bring a new AWS account (a new "system") into the dashboard
after the analytics hub is already deployed. It has two parts:

1. **Deploy the sender** into the new source account so its data flows to the hub.
2. **Add a dashboard sheet** for the new system in QuickSight by duplicating an existing
   System sheet and re-pointing its filter.

> Terminology: on the dashboard each tab is a **System** (e.g. *System A*).
> A system maps to one or more source accounts through the `products` /
> `product_accounts` tables. The per-system sheets and the Overview cards filter on the
> **`system_name`** column, whose value comes from the product name you register.

> **Read this first:** [What auto-populates vs. what you must edit by hand](#what-auto-populates-vs-what-you-configure-by-hand).
> The dashboard ships with **placeholder** system names (*System A* … *System F*). The
> data-driven parts fill in on their own once your senders run, but the system **labels**
> and the **per-visual filters** are placeholders you must point at your real system names.

---

## Prerequisites

- The analytics hub is deployed (`cloudformation/A360-Analytics.yaml`) and the QuickSight
  dashboard has been provisioned (see the [QuickSight guide](../quicksight/README.md)).
- You can administer QuickSight in the hub account.
- You have access to the new source account to deploy the sender stack.

---

## What auto-populates vs. what you configure by hand

The dashboard ships with generic placeholder names — **System A** through **System F** on
the Overview page, and one detail sheet named **System A**. Understanding what is
data-driven and what is a hand-set placeholder saves a lot of confusion on first deploy.

### Auto-populates from your data (no edit needed)

These read live from Aurora as soon as your senders/collectors write data. You never edit
them per deployment:

- **Every metric value**: health scores, alarm counts, security findings, availability,
  costs, resource inventory — all computed from the collected data.
- **Account IDs and account names** shown in tables (e.g. Account Summary) — these come
  straight from the `accounts` rows the receiver creates from each sender's first run.
- **The list of systems on the Overview** aggregates across whatever is in `products` —
  a new system shows up on the Overview automatically once registered.
- **The `system_name` values themselves** in the data come from `products.name`
  (the `ProductName` you set on each sender).

### You configure by hand (per deployment)

These are **placeholders baked into the analysis layout** that QuickSight cannot derive
from data, because the card titles are static text and each card is pinned to one system:

1. **Overview card titles** — the bold "System A" … "System F" headings are **hard-coded
   rich text** on each KPI card. Rename them to your real system names (e.g. *Payments
   Platform*, *Customer Portal*).
2. **Per-visual `system_name` filters** — every tile on the Overview (the KPI, Service
   Availability, Critical Alarms, Warnings, Health Score Label, Health Status Icon) and
   every visual on a detail sheet has its **own filter** that includes exactly one
   `system_name` value. The shipped values are the placeholders `System A`…`System F`. You
   must change each card's filter to the matching real `system_name` **for every tile in
   that card's column**, or the card will show another system's data (or "No data").
3. **Detail-sheet name + filters** — the **System A** detail sheet's tab name and all its
   visual filters are placeholders; rename and re-point them, and duplicate the sheet for
   each additional system (see Part 2).

> Why isn't this automatic? QuickSight analyses store visual titles as static text and
> pin each visual to a fixed filter value at design time — there is no "current row"
> binding for a KPI card title or a per-card filter. So the layout ships with placeholders
> and you map them to your systems once. After that, all the numbers stay live.

**How many cards?** The Overview ships with 6 system slots (A–F). If you have fewer
systems, the extra cards simply show "No data" — either leave them, delete the unused
cards, or repurpose them. If you have more than 6, copy an existing card column and set its
title + filters to the new system.

---

## Part 1 — Deploy the sender into the new source account

1. Sign in to the **new source account**.
2. In CloudFormation, create a stack from `cloudformation/A360-Sender.yaml`.
3. Set the parameters:
   - **AnalyticsAccount** — the hub account ID.
   - **S3Bucket** / **AnalyticsKMSKey** — the hub S3 bucket and KMS key ARN (from the
     analytics stack outputs).
   - **ProductName** — the human-readable system name for this account (for example,
     `Payments Platform`). This is the value that becomes `system_name` on the dashboard,
     so choose the label you want the System sheet to show.
   - Other tags (Category / Environment) as appropriate for your organization.
4. Create the stack, then open the **Sender** Lambda and run a **Test** invocation to send
   the first batch immediately (otherwise it runs on the daily schedule).
5. (Optional, for near-real-time metrics/alarms) enable CloudWatch cross-account
   observability (OAM) so the hub's Metric Collector can read this account's metrics.

### Register the product → account mapping

In the hub's Aurora **Query Editor**, register the system and map it to the new account
(see [`sql/a360-sql-helper.md`](../sql/a360-sql-helper.md) §2). Replace the placeholders:

```sql
-- 1. Create the product (system) if it does not exist yet
INSERT INTO products (name, owner, position, description) VALUES
('<PRODUCT_NAME>', '<OWNER_NAME>', '<OWNER_TITLE>', '<PRODUCT_DESCRIPTION>');

-- 2. Map it to the new source account
INSERT INTO product_accounts (product_id, account_id)
SELECT p.id, a.id
FROM products p
JOIN accounts a ON a.account_id IN ('<NEW_SOURCE_ACCOUNT_ID>')
WHERE p.name = '<PRODUCT_NAME>';
```

Use the **same** `<PRODUCT_NAME>` you set as `ProductName` on the sender stack so the data
and the dashboard filter line up.

### Verify data is arriving

Within a few minutes of the first sender run (and the 5-minute metric collection cycle),
confirm the new account is registered and mapped to its product:

```sql
-- The account row created by the receiver from the sender's first run
SELECT account_id, account_name FROM accounts WHERE account_id = '<NEW_SOURCE_ACCOUNT_ID>';

-- The product-to-account mapping you registered
SELECT p.name AS system_name, a.account_id
FROM products p
JOIN product_accounts pa ON pa.product_id = p.id
JOIN accounts a ON a.id = pa.account_id
ORDER BY p.name;
```

The new system should appear on the dashboard **Overview** sheet automatically, because the
Overview visuals aggregate across all systems. If it does not appear yet, wait for the next
collection cycle (senders run daily; metrics/alarms collect every 5 minutes) and re-check.

---

## Part 2 — Point the Overview cards and add a detail sheet

The dashboard ships with **two sheets**: **Overview** (the cross-system cards) and one
detail sheet, **System A**. Wiring a system into the dashboard is two steps: point its
Overview card at it, then give it a detail sheet by duplicating **System A**.

### 2a. Point an Overview card at your system

The Overview has 6 card columns (System A … System F). For the column you want to use:

1. Open the analysis: **Analyses → the observability analysis → Edit**, select the
   **Overview** sheet.
2. **Rename the card title.** Click the card's title text (e.g. "System C"), and edit the
   rich text to your real system name.
3. **Re-point every tile in that column.** Each tile in the column has its own
   `system_name` filter. For each tile (the big Health Score KPI, Service Availability,
   Critical Alarms, Warnings, Health Score Label, Health Status Icon):
   - Select the tile → open the **Filter** pane (it shows "Only this visual").
   - Find the `system_name` filter and change its included value to your real
     `system_name` (the `<PRODUCT_NAME>` you registered). It must match the data exactly.
   - Apply.
4. Repeat for each system column you use.

> The shipped card filters use the placeholders `System A`…`System F`. Until you change
> them, a card shows data only if a system with that exact placeholder name exists — which
> is why unused cards read "No data".

### 2b. Add a detail sheet for the system

The **System A** sheet is the template. To add a detail sheet for another system:

1. Right-click the **System A** sheet tab and choose **Duplicate**.
2. Rename the new sheet to your system's display name (for example, *Payments Platform*).
3. Re-point the sheet's filters:
   - Open the **Filter** pane while the new sheet is selected.
   - Change **every** filter that references `system_name` from `System A` to your new
     system's `system_name` (duplicated sheets carry over all of the source sheet's
     filters, so there is usually more than one — the System Availability table and any
     per-visual scoped filters). Confirm none still reference `System A`.
   - Apply.
4. **(Optional) wire the drill-down.** Overview cards have a click-through action that
   navigates to the **System A** detail sheet. To make a card open its own new sheet
   instead, select the card → **Actions** → edit the navigation action's target sheet.
   Leaving it as-is simply always lands on the System A sheet.
5. **Publish** the analysis to the dashboard (**Share → Publish dashboard → replace the
   existing dashboard**).

> Tip: before you customize it, **duplicate System A once and keep the copy untouched** as
> your clean template for future systems.

### Checklist

- [ ] Sender stack deployed in the new account with the correct `ProductName`.
- [ ] First sender run completed (manual Test invocation).
- [ ] Product created and mapped to the account in `products` / `product_accounts`.
- [ ] `SELECT DISTINCT system_name ...` shows the new system.
- [ ] Overview card **title renamed** and **all tiles in the column re-pointed** to the
      real `system_name`.
- [ ] Detail sheet duplicated from System A, renamed, and all `system_name` filters
      re-pointed (and drill-down action retargeted if desired).
- [ ] Dashboard re-published.

---

## Removing a system

To stop tracking a system: delete the sender stack in the source account, remove the sheet
in QuickSight, and (optionally) delete the product mapping:

```sql
DELETE FROM product_accounts
WHERE product_id = (SELECT id FROM products WHERE name = '<PRODUCT_NAME>');
DELETE FROM products WHERE name = '<PRODUCT_NAME>';
```
