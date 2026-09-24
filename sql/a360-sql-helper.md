# This file is a utility guide for you to implement other tasks

## 1. Drop all views within the database
Copy paste it in the quyery editor to remove the views

```
DROP VIEW IF EXISTS view_waf_rules_detailed;
DROP VIEW IF EXISTS view_waf_rules;
DROP VIEW IF EXISTS view_trusted_advisor_checks;
DROP VIEW IF EXISTS view_summary;
DROP VIEW IF EXISTS view_service_resources_summary;
DROP VIEW IF EXISTS view_service_resources;
DROP VIEW IF EXISTS view_secrets_manager_secrets;
DROP VIEW IF EXISTS view_resilience_hub_apps;
DROP VIEW IF EXISTS view_products;
DROP VIEW IF EXISTS view_product_summary;
DROP VIEW IF EXISTS view_product_acct;
DROP VIEW IF EXISTS view_marketplace_usage;
DROP VIEW IF EXISTS view_kms_keys;
DROP VIEW IF EXISTS view_inventory_patches;
DROP VIEW IF EXISTS view_inventory_instances;
DROP VIEW IF EXISTS view_inventory_applications;
DROP VIEW IF EXISTS view_inspector_findings;
DROP VIEW IF EXISTS view_health_events;
DROP VIEW IF EXISTS view_guard_duty_findings;
DROP VIEW IF EXISTS view_contact_info;
DROP VIEW IF EXISTS view_config_reports;
DROP VIEW IF EXISTS view_non_compliant_resources;
DROP VIEW IF EXISTS view_config_inventory_summary;
DROP VIEW IF EXISTS view_config_inventory_account_summary;
DROP VIEW IF EXISTS view_config_inventory;
DROP VIEW IF EXISTS view_compute_optimizer;
DROP VIEW IF EXISTS view_cloudtrail_logs;
DROP VIEW IF EXISTS view_certificates;
DROP VIEW IF EXISTS view_application_signals;
DROP VIEW IF EXISTS view_alternate_contacts;
DROP VIEW IF EXISTS view_acct_summary;
DROP VIEW IF EXISTS view_acct_serv_cost;
DROP VIEW IF EXISTS view_acct_serv;
DROP VIEW IF EXISTS view_acct_security_findings_summary;
DROP VIEW IF EXISTS view_acct_security_findings_details;
DROP VIEW IF EXISTS view_acct_security;
DROP VIEW IF EXISTS view_acct_products;
DROP VIEW IF EXISTS view_acct_logs;
DROP VIEW IF EXISTS view_acct_log_messages;
DROP VIEW IF EXISTS view_acct_cost_rep_forecast;
DROP VIEW IF EXISTS view_acct_cost_rep;
DROP VIEW IF EXISTS view_accounts;
DROP VIEW IF EXISTS view_support_tickets;
DROP VIEW IF EXISTS view_ri_sp_daily_savings;
```

## 2. Managing products via Query editor

A "product" (also referred to as a *system* on the dashboard) is a logical grouping of one or
more AWS accounts. Registering products lets the dashboard filter each System sheet to the
accounts that belong to that system. This is **configuration**, not data — you define your own
products and map them to your own accounts. No sample rows are shipped with this solution;
until you register your products the product views simply return no rows.

> Replace every placeholder below (shown in `<...>`) with your own values before running.

### 2.1 Creating a product

```sql
INSERT INTO products (name, owner, position, description) VALUES
('<PRODUCT_NAME>', '<OWNER_NAME>', '<OWNER_TITLE>', '<PRODUCT_DESCRIPTION>');
```

### 2.2 Associating a product to its accounts

```sql
-- Map an existing product to one or more of your onboarded account IDs
INSERT INTO product_accounts (product_id, account_id)
SELECT p.id, a.id
FROM products p
JOIN accounts a ON a.account_id IN ('<ACCOUNT_ID_1>', '<ACCOUNT_ID_2>')
WHERE p.name = '<PRODUCT_NAME>';
```

## 3. TRUNCATE all records in the database

```
-- Truncate all tables with CASCADE
TRUNCATE TABLE 
    accounts,
    contact_info,
    alternate_contacts,
    services,
    cost_reports,
    service_costs,
    cost_forecasts,
    security,
    findings,
    products,
    product_accounts,
    logs,
    log_messages,
    config_reports,
    non_compliant_resources,
    service_resources,
    compute_optimizer,
    config_inventory,
    guard_duty_findings,
    kms_keys,
    waf_rules,
    waf_rules_detailed,
    cloudtrail_logs,
    secrets_manager_secrets,
    certificates,
    inspector_findings,
    inventory_instances,
    inventory_applications,
    inventory_patches,
    marketplace_usage,
    trusted_advisor_checks,
    health_events,
    application_signals,
    resilience_hub_apps,
    support_tickets,
    ri_sp_daily_savings
RESTART IDENTITY CASCADE;

```