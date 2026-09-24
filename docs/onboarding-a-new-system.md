# Onboarding a New System (Source Account)

This guide explains how to bring a new AWS account (a new "system") into the dashboard
after the analytics hub is already deployed. It has two parts:

1. **Deploy the sender** into the new source account so its data flows to the hub.
2. **Add a dashboard sheet** for the new system in QuickSight by duplicating an existing
   System sheet and re-pointing its filter.

> Terminology: on the dashboard each tab is a **System** (e.g. *System A*, *System B*).
> A system maps to one or more source accounts through the `products` /
> `product_accounts` tables. The per-system sheets filter on the **`system_name`** column,
> whose value comes from the product name you register.

---

## Prerequisites

- The analytics hub is deployed (`cloudformation/A360-Analytics.yaml`) and the QuickSight
  dashboard has been provisioned (see the [QuickSight guide](../quicksight/README.md)).
- You can administer QuickSight in the hub account.
- You have access to the new source account to deploy the sender stack.

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

## Part 2 — Add a dedicated sheet for the new system

The per-system sheets (*System A*, *System B*) are pinned to a single system via a
sheet-scoped filter on `system_name`. To add *System C* (etc.), duplicate an existing sheet
and change that filter.

1. Open the analysis in QuickSight: **Analyses → View 360 Observability Dashboard → Edit**.
2. Right-click the **System B** sheet tab (it is provided as the template to copy) and
   choose **Duplicate**.
3. Rename the new sheet to your system's display name (for example, *System C* or
   *Payments Platform*).
4. Update the sheet's system filter:
   - Open the **Filter** pane while the new sheet is selected.
   - Find the filter on the **`system_name`** field that is **scoped to this sheet only**.
   - Change its selected value from `System B` to your new system's `system_name`
     (the `<PRODUCT_NAME>` you registered) — this must match the data exactly.
   - Apply.
5. Repeat for every visual-scoped filter on the sheet that references `system_name`
   (duplicated sheets carry over the original sheet's filters, so there may be more than
   one). Confirm none still reference the old value.
6. **Publish** the analysis to the dashboard (**Share → Publish dashboard → replace the
   existing dashboard**).

> Tip: keep **System B** as an untouched "template" sheet so you always have a clean sheet
> to duplicate for the next system.

### Checklist

- [ ] Sender stack deployed in the new account with the correct `ProductName`.
- [ ] First sender run completed (manual Test invocation).
- [ ] Product created and mapped to the account in `products` / `product_accounts`.
- [ ] `SELECT DISTINCT system_name ...` shows the new system.
- [ ] New sheet duplicated, renamed, and all `system_name` filters re-pointed.
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
