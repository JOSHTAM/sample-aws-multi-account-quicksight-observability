-- Views for all tables with additional columns
-- account: account_id from accounts table
-- account_full: account_id + "-" + account_name
-- project_product_name: product name from products table via product_accounts junction

-- 1. Accounts view
CREATE OR REPLACE VIEW view_accounts AS
SELECT
    a.*,
    a.account_id as account,
    a.category as account_category,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    accounts a
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

-- 2. Contact info view
CREATE OR REPLACE VIEW view_contact_info AS
SELECT
    ci.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    contact_info ci
    JOIN accounts a ON ci.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

-- 3. Alternate contacts view
CREATE OR REPLACE VIEW view_alternate_contacts AS
SELECT
    ac.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    alternate_contacts ac
    JOIN accounts a ON ac.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

-- 4. Services view
CREATE OR REPLACE VIEW view_acct_serv AS
SELECT
    s.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    services s
    JOIN accounts a ON s.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

-- 5. Cost reports view
CREATE OR REPLACE VIEW view_acct_cost_rep AS
SELECT
    cr.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    cr.period_start as date_from,
    cr.period_end as date_to
FROM
    cost_reports cr
    JOIN accounts a ON cr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--6.  Service costs view
CREATE OR REPLACE VIEW view_acct_serv_cost AS
SELECT
    sc.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    cr.period_start as date_from,
    cr.period_end as date_to
FROM
    service_costs sc
    JOIN cost_reports cr ON sc.cost_report_id = cr.id
    JOIN accounts a ON cr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--7. Cost forecasts view
CREATE OR REPLACE VIEW view_acct_cost_rep_forecast AS
SELECT
    cf.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    cr.period_start as date_from,
    cr.period_end as date_to
FROM
    cost_forecasts cf
    JOIN cost_reports cr ON cf.cost_report_id = cr.id
    JOIN accounts a ON cr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--8. Security view
CREATE OR REPLACE VIEW view_acct_security AS
SELECT
    s.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    security s
    JOIN accounts a ON s.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--9. Findings view
CREATE OR REPLACE VIEW view_acct_security_findings_details AS
SELECT
    f.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    findings f
    JOIN security s ON f.security_id = s.id
    JOIN accounts a ON s.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--10. Products view
CREATE OR REPLACE VIEW view_products AS
SELECT
    pr.*,
    NULL as account,
    NULL as account_region,
    NULL as account_name,
    NULL as account_type,
    NULL as account_category,
    NULL as account_status,
    NULL as account_partner,
    NULL as account_customer,
    NULL as account_full,
    pr.name as project_product_name
FROM
    products pr;

--11. Product accounts view
CREATE OR REPLACE VIEW view_product_acct AS
SELECT
    pa.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    product_accounts pa
    JOIN accounts a ON pa.account_id = a.id
    JOIN products p ON pa.product_id = p.id;

--12. Products view with account relationships (CORRECTED)
CREATE OR REPLACE VIEW view_acct_products AS
SELECT
    p.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    pr.name as project_product_name
FROM
    products p
    JOIN product_accounts pa ON p.id = pa.product_id
    JOIN accounts a ON pa.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa2 ON a.id = pa2.account_id
    LEFT JOIN products pr ON pa2.product_id = pr.id;

--13. Logs view
CREATE OR REPLACE VIEW view_acct_logs AS
SELECT
    l.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as acct_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    logs l
    JOIN accounts a ON l.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--14. Log messages view
CREATE OR REPLACE VIEW view_acct_log_messages AS
SELECT
    lm.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    log_messages lm
    JOIN logs l ON lm.log_id = l.id
    JOIN accounts a ON l.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--15. Config reports view
CREATE OR REPLACE VIEW view_config_reports AS
SELECT
    cr.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    config_reports cr
    JOIN accounts a ON cr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--16. Non compliant resources view
CREATE OR REPLACE VIEW view_non_compliant_resources AS
SELECT
    ncr.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    non_compliant_resources ncr
    JOIN config_reports cr ON ncr.config_report_id = cr.id
    JOIN accounts a ON cr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--17. Service resources view
CREATE OR REPLACE VIEW view_service_resources AS
SELECT
    sr.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT(a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    service_resources sr
    JOIN accounts a ON sr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;


--18. Create summary view
CREATE OR REPLACE VIEW view_service_resources_summary AS
SELECT
    a.account_id,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    sr.service_name,
    sr.resource_type,
    sr.region as resource_region,
    sr.availability_zone,
    COUNT(*) as resource_count,
    COUNT(CASE WHEN sr.state IN ('running', 'available', 'Active') THEN 1 END) as active_resources,
    COUNT(CASE WHEN sr.state IN ('stopped', 'Inactive') THEN 1 END) as inactive_resources
FROM service_resources sr
LEFT JOIN accounts a ON sr.account_id = a.id
GROUP BY a.account_id, a.region, a.account_name, a.account_type, a.category, a.account_status, a.partner_name, a.customer_name, sr.service_name, sr.resource_type, sr.region, sr.availability_zone;

--19. Compute optimizers view
CREATE OR REPLACE VIEW view_compute_optimizer AS
SELECT
    co.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,    
    CONCAT(a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    compute_optimizer co
    LEFT JOIN accounts a ON co.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--20. Guard duty findings view
CREATE OR REPLACE VIEW view_guard_duty_findings AS
SELECT
    gdf.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    guard_duty_findings gdf
    JOIN accounts a ON gdf.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--21. KMS keys view
CREATE OR REPLACE VIEW view_kms_keys AS
SELECT
    kk.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    kms_keys kk
    JOIN accounts a ON kk.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--22. WAF rules view
CREATE OR REPLACE VIEW view_waf_rules AS
SELECT
    wr.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,    
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    waf_rules wr
    JOIN accounts a ON wr.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--23. WAF Rules detailed view
CREATE OR REPLACE VIEW view_waf_rules_detailed AS
SELECT
    wrd.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    waf_rules_detailed wrd
    JOIN accounts a ON wrd.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--24. CloudTrail logs view
CREATE OR REPLACE VIEW view_cloudtrail_logs AS
SELECT
    ctl.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    cloudtrail_logs ctl
    JOIN accounts a ON ctl.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--25. Secrets manager secrets view
CREATE OR REPLACE VIEW view_secrets_manager_secrets AS
SELECT
    sms.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    secrets_manager_secrets sms
    JOIN accounts a ON sms.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--26. Certificates view
CREATE OR REPLACE VIEW view_certificates AS
SELECT
    c.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    certificates c
    JOIN accounts a ON c.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--27. Inspector findings view
CREATE OR REPLACE VIEW view_inspector_findings AS
SELECT
    if.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    inspector_findings if
    JOIN accounts a ON if.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--28. Inventory instances view
CREATE OR REPLACE VIEW view_inventory_instances AS
SELECT
    ii.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    inventory_instances ii
    JOIN accounts a ON ii.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--29. Inventory applications view
CREATE OR REPLACE VIEW view_inventory_applications AS
SELECT
    ia.name,
    -- inventory_instances attributes (prefixed to avoid conflicts)
    ii.id as ii_id,
    ii.account_id as ii_account_id,
    ii.instance_id as ii_instance_id,
    ii.instance_type,
    ii.platform,
    ii.ip_address,
    ii.computer_name,
    ii.ping_status,
    ii.last_ping_date_time,
    ii.agent_version,
    ii.platform_type,
    ii.platform_version,
    ii.is_latest_version,
    ii.association_status,
    ii.association_execution_date,
    ii.association_success_date,
    ii.created_at as ii_created_at,
    -- account attributes
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    inventory_applications ia
    JOIN inventory_instances ii ON ia.instance_id = ii.id
    JOIN accounts a ON ia.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--30. Inventory patches view
CREATE OR REPLACE VIEW view_inventory_patches AS
SELECT
    ip.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    ii.instance_id as instance_name,
    ii.instance_type
FROM
    inventory_patches ip
    JOIN inventory_instances ii ON ip.instance_id = ii.id
    JOIN accounts a ON ip.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--31. Marketplace usage view
CREATE OR REPLACE VIEW view_marketplace_usage AS
SELECT
    mu.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    marketplace_usage mu
    JOIN accounts a ON mu.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--32. Trusted advisor checks view
CREATE OR REPLACE VIEW view_trusted_advisor_checks AS
SELECT
    tac.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    trusted_advisor_checks tac
    JOIN accounts a ON tac.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--33. Health events view
CREATE OR REPLACE VIEW view_health_events AS
SELECT
    he.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    health_events he
    JOIN accounts a ON he.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--34. Application signals view
CREATE OR REPLACE VIEW view_application_signals AS
SELECT
    as_.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    application_signals as_
    JOIN accounts a ON as_.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--35. Resilience hub apps view
CREATE OR REPLACE VIEW view_resilience_hub_apps AS
SELECT
    rha.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    resilience_hub_apps rha
    JOIN accounts a ON rha.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--36. Summary view with product count only
CREATE OR REPLACE VIEW view_summary AS
SELECT
    -- Account Identifiers
    a.id as account_id,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT(a.account_id, '-', a.account_name) as account_full,
    a.csp as account_csp,

    -- Product Count
    COALESCE(pc.number_of_products, 0) as number_of_products,

    -- Cost Metrics
    cr.period_granularity,
    cr.period_start as date_from,
    cr.period_end as date_to,
    ROUND(cr.current_period_cost, 2) as current_period_cost,
    ROUND(cr.previous_period_cost, 2) as previous_period_cost,
    ROUND(cr.cost_difference, 2) as cost_difference,
    ROUND(cr.cost_difference_percentage, 4) as cost_difference_percentage,
    ROUND(cr.potential_monthly_savings, 2) as potential_savings,

    -- Service Metrics
    sm.service_count,
    sm.unique_services,
    ROUND(sm.total_service_cost, 2) as total_service_cost,
    sm.services_used,

    -- Security Metrics
    sec.total_findings,
    sec.open_findings,
    sec.resolved_findings,
    sec.critical_findings,
    sec.high_findings,
    sec.medium_findings,
    sec.low_findings,

    -- Calculated Security Metrics
    ROUND(sec.resolved_findings::DECIMAL / NULLIF(sec.total_findings, 0), 4) as security_resolution_rate,

    -- Account Information
    a.account_email,
    a.joined_method,
    a.joined_timestamp,
    EXTRACT(DAY FROM AGE(CURRENT_TIMESTAMP, a.joined_timestamp)) as account_age_days
FROM accounts a
LEFT JOIN (
    SELECT DISTINCT ON (account_id, period_granularity)
        account_id, period_granularity, period_start, period_end,
        current_period_cost, previous_period_cost, cost_difference,
        cost_difference_percentage, potential_monthly_savings
    FROM cost_reports
    ORDER BY account_id, period_granularity, period_end DESC
) cr ON cr.account_id = a.id
LEFT JOIN (
    SELECT
        account_id,
        COUNT(DISTINCT id) as service_count,
        COUNT(DISTINCT service) as unique_services,
        SUM(cost) as total_service_cost,
        STRING_AGG(DISTINCT service, ', ') as services_used
    FROM services
    GROUP BY account_id
) sm ON sm.account_id = a.id
LEFT JOIN (
    SELECT
        account_id,
        SUM(total_findings) as total_findings,
        SUM(open_findings) as open_findings,
        SUM(resolved_findings) as resolved_findings,
        SUM(critical_count) as critical_findings,
        SUM(high_count) as high_findings,
        SUM(medium_count) as medium_findings,
        SUM(low_count) as low_findings
    FROM security
    GROUP BY account_id
) sec ON sec.account_id = a.id
LEFT JOIN (
    SELECT
        account_id,
        COUNT(DISTINCT product_id) as number_of_products
    FROM product_accounts
    GROUP BY account_id
) pc ON pc.account_id = a.id
WHERE
    (cr.period_granularity IS NULL OR
     cr.period_granularity::text IN ('MONTHLY', 'WEEKLY', 'DAILY'))
ORDER BY
    a.account_name,
    cr.period_start DESC;

--37. Account summary view (CORRECTED - single version)
CREATE OR REPLACE VIEW view_acct_summary AS
SELECT
    a.*,
    a.account_id as account,
    a.region as account_region,
    a.category as account_category,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    -- Cost metrics
    COALESCE(cr.current_period_cost, 0) as latest_cost,
    COALESCE(cr.cost_difference_percentage, 0) as cost_trend_percentage,
    COALESCE(cr.potential_monthly_savings, 0) as savings_opportunity,
    -- Security metrics
    COALESCE(s.total_findings, 0) as security_findings,
    COALESCE(s.critical_count, 0) as critical_findings,
    COALESCE(s.high_count, 0) as high_findings,
    -- Inventory metrics
    COALESCE(i.instance_count, 0) as instance_count,
    COALESCE(i.running_instances, 0) as running_instances,
    -- Health score calculation
    CASE
        WHEN s.critical_count > 0 THEN 1
        WHEN s.high_count > 0 THEN 2
        WHEN s.medium_count > 0 THEN 3
        WHEN s.low_count > 0 THEN 4
        ELSE 5
    END as security_health_score
FROM
    accounts a
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id
    LEFT JOIN (
        SELECT account_id, current_period_cost, cost_difference_percentage, potential_monthly_savings
        FROM cost_reports
        WHERE period_granularity = 'MONTHLY'
        ORDER BY period_end DESC
        LIMIT 1
    ) cr ON cr.account_id = a.id
    LEFT JOIN (
        SELECT account_id, total_findings, critical_count, high_count, medium_count, low_count
        FROM security
        ORDER BY created_at DESC
        LIMIT 1
    ) s ON s.account_id = a.id
    LEFT JOIN (
        SELECT
            account_id,
            COUNT(*) as instance_count,
            COUNT(CASE WHEN ping_status = 'Online' THEN 1 END) as running_instances
        FROM inventory_instances
        GROUP BY account_id
    ) i ON i.account_id = a.id;

--38. Product summary view with individual products
CREATE OR REPLACE VIEW view_product_summary AS
SELECT
    -- Account Identifiers
    a.id as account_id,
    a.account_id as account,
    a.region as account_region,
    a.account_name,

    CONCAT(a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    a.csp as account_csp,
    a.account_type as account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,

    -- Product Details
    p.id as product_id,
    p.owner as product_owner,
    p.position as product_position,
    p.description as product_description,

    -- Cost Metrics
    cr.period_granularity,
    cr.period_start as date_from,
    cr.period_end as date_to,
    ROUND(cr.current_period_cost, 2) as current_period_cost,
    ROUND(cr.previous_period_cost, 2) as previous_period_cost,
    ROUND(cr.cost_difference, 2) as cost_difference,
    ROUND(cr.cost_difference_percentage, 4) as cost_difference_percentage,
    ROUND(cr.potential_monthly_savings, 2) as potential_savings,

    -- Service Metrics
    sm.service_count,
    sm.unique_services,
    ROUND(sm.total_service_cost, 2) as total_service_cost,
    sm.services_used,

    -- Security Metrics
    sec.total_findings,
    sec.open_findings,
    sec.resolved_findings,
    sec.critical_findings,
    sec.high_findings,
    sec.medium_findings,
    sec.low_findings,

    -- Calculated Security Metrics
    ROUND(sec.resolved_findings::DECIMAL / NULLIF(sec.total_findings, 0), 4) as security_resolution_rate,

    -- Account Information
    a.account_email,
    a.joined_method,
    a.joined_timestamp,
    EXTRACT(DAY FROM AGE(CURRENT_TIMESTAMP, a.joined_timestamp)) as account_age_days
FROM accounts a
LEFT JOIN product_accounts pa ON a.id = pa.account_id
LEFT JOIN products p ON pa.product_id = p.id
LEFT JOIN (
    SELECT DISTINCT ON (account_id, period_granularity)
        account_id, period_granularity, period_start, period_end,
        current_period_cost, previous_period_cost, cost_difference,
        cost_difference_percentage, potential_monthly_savings
    FROM cost_reports
    ORDER BY account_id, period_granularity, period_end DESC
) cr ON cr.account_id = a.id
LEFT JOIN (
    SELECT
        account_id,
        COUNT(DISTINCT id) as service_count,
        COUNT(DISTINCT service) as unique_services,
        SUM(cost) as total_service_cost,
        STRING_AGG(DISTINCT service, ', ') as services_used
    FROM services
    GROUP BY account_id
) sm ON sm.account_id = a.id
LEFT JOIN (
    SELECT
        account_id,
        SUM(total_findings) as total_findings,
        SUM(open_findings) as open_findings,
        SUM(resolved_findings) as resolved_findings,
        SUM(critical_count) as critical_findings,
        SUM(high_count) as high_findings,
        SUM(medium_count) as medium_findings,
        SUM(low_count) as low_findings
    FROM security
    GROUP BY account_id
) sec ON sec.account_id = a.id
WHERE
    (cr.period_granularity IS NULL OR
     cr.period_granularity::text IN ('MONTHLY', 'WEEKLY', 'DAILY'))
ORDER BY
    a.account_name,
    p.name,
    cr.period_start DESC;

--39. Security findings summary view
CREATE OR REPLACE VIEW view_acct_security_findings_summary AS
SELECT
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    s.service,
    s.total_findings,
    s.critical_count,
    s.high_count,
    s.medium_count,
    s.low_count,
    s.informational_count,
    s.open_findings,
    s.resolved_findings,
    -- Calculated fields using available data
    0 as suppressed_count,
    0 as in_progress_count,
    s.open_findings as active_issues,
    'N/A' as region_finding,
    s.resolved_findings as resolved_count,
    CASE
        WHEN s.critical_count > 0 THEN 'CRITICAL'
        WHEN s.high_count > 0 THEN 'HIGH'
        WHEN s.medium_count > 0 THEN 'MEDIUM'
        WHEN s.low_count > 0 THEN 'LOW'
        WHEN s.informational_count > 0 THEN 'INFORMATIONAL'
        ELSE 'CLEAN'
    END as severity,
    -- Calculated metrics
    ROUND(s.resolved_findings::DECIMAL / NULLIF(s.total_findings, 0) * 100, 2) as resolution_rate_percent,
    CASE
        WHEN s.critical_count > 0 THEN 'Critical'
        WHEN s.high_count > 0 THEN 'High'
        WHEN s.medium_count > 0 THEN 'Medium'
        WHEN s.low_count > 0 THEN 'Low'
        ELSE 'Clean'
    END as risk_level,
    s.created_at,
    s.updated_at
FROM
    security s
    JOIN accounts a ON s.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--40. Compute Optimizer View
CREATE OR REPLACE VIEW view_compute_optimizer_summary AS
SELECT
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT(a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name,
    co.resource_type,
    co.finding,
    COUNT(*) as resource_count,
    SUM(co.estimated_monthly_savings_usd) as total_monthly_savings,
    AVG(co.savings_opportunity_percentage) as avg_savings_percentage,
    AVG(co.performance_risk) as avg_performance_risk,
    COUNT(CASE WHEN co.finding = 'NotOptimized' THEN 1 END) as not_optimized_count,
    COUNT(CASE WHEN co.estimated_monthly_savings_usd > 0 THEN 1 END) as savings_opportunities
FROM compute_optimizer co
LEFT JOIN accounts a ON co.account_id = a.id
LEFT JOIN (
    SELECT DISTINCT ON (account_id) account_id, product_id
    FROM product_accounts
    ORDER BY account_id, id
) pa ON a.id = pa.account_id
LEFT JOIN products p ON pa.product_id = p.id
GROUP BY a.account_id, a.region, a.account_name, a.account_type, a.category, a.account_status, a.partner_name, a.customer_name, p.name, co.resource_type, co.finding;

--41. Create a Support Tickets View
CREATE OR REPLACE VIEW view_acct_support_tickets AS
SELECT
    st.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT (a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    support_tickets st
    JOIN accounts a ON st.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--42. Create a Savings Plan and Reserved Instances View
CREATE OR REPLACE VIEW view_ri_sp_daily_savings AS
SELECT
    r.*,
    a.account_id as account,
    a.region as account_region,
    a.account_name,
    a.account_type,
    a.category as account_category,
    a.account_status as account_status,
    a.partner_name as account_partner,
    a.customer_name as account_customer,
    CONCAT(a.account_id, '-', a.account_name) as account_full,
    p.name as project_product_name
FROM
    ri_sp_daily_savings r
    JOIN accounts a ON r.account_id = a.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON a.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;


-- ============================================================================
-- Executive Alerts Dashboard Views
-- ============================================================================

--43. Alarms view with account enrichment
CREATE OR REPLACE VIEW view_alarms AS
SELECT
    a.*,
    acc.account_id as account,
    acc.region as account_region,
    acc.account_name,
    acc.account_type,
    acc.category as account_category,
    acc.account_status as account_status,
    acc.partner_name as account_partner,
    acc.customer_name as account_customer,
    CONCAT(acc.account_id, '-', acc.account_name) as account_full,
    p.name as project_product_name
FROM
    alarms a
    JOIN accounts acc ON a.account_id = acc.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON acc.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--44. Canaries view with account enrichment
CREATE OR REPLACE VIEW view_canaries AS
SELECT
    c.*,
    acc.account_id as account,
    acc.region as account_region,
    acc.account_name,
    acc.account_type,
    acc.category as account_category,
    acc.account_status as account_status,
    acc.partner_name as account_partner,
    acc.customer_name as account_customer,
    CONCAT(acc.account_id, '-', acc.account_name) as account_full,
    p.name as project_product_name
FROM
    canaries c
    JOIN accounts acc ON c.account_id = acc.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON acc.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--45. Incidents view with account enrichment
CREATE OR REPLACE VIEW view_incidents AS
SELECT
    i.*,
    acc.account_id as account,
    acc.region as account_region,
    acc.account_name,
    acc.account_type,
    acc.category as account_category,
    acc.account_status as account_status,
    acc.partner_name as account_partner,
    acc.customer_name as account_customer,
    CONCAT(acc.account_id, '-', acc.account_name) as account_full,
    p.name as project_product_name
FROM
    incidents i
    JOIN accounts acc ON i.account_id = acc.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON acc.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--46. Error summaries view with account enrichment
CREATE OR REPLACE VIEW view_error_summaries AS
SELECT
    es.*,
    acc.account_id as account,
    acc.region as account_region,
    acc.account_name,
    acc.account_type,
    acc.category as account_category,
    acc.account_status as account_status,
    acc.partner_name as account_partner,
    acc.customer_name as account_customer,
    CONCAT(acc.account_id, '-', acc.account_name) as account_full,
    p.name as project_product_name
FROM
    error_summaries es
    JOIN accounts acc ON es.account_id = acc.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON acc.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--47. Database insights view with account enrichment
CREATE OR REPLACE VIEW view_db_insights AS
SELECT
    di.*,
    acc.account_id as account,
    acc.region as account_region,
    acc.account_name,
    acc.account_type,
    acc.category as account_category,
    acc.account_status as account_status,
    acc.partner_name as account_partner,
    acc.customer_name as account_customer,
    CONCAT(acc.account_id, '-', acc.account_name) as account_full,
    p.name as project_product_name
FROM
    db_insights di
    JOIN accounts acc ON di.account_id = acc.id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON acc.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id;

--48. Executive summary aggregation view
CREATE OR REPLACE VIEW view_executive_summary AS
SELECT
    acc.id as id,
    acc.account_id as account,
    acc.region as account_region,
    acc.account_name,
    acc.account_type,
    acc.category as account_category,
    acc.account_status as account_status,
    acc.partner_name as account_partner,
    acc.customer_name as account_customer,
    CONCAT(acc.account_id, '-', acc.account_name) as account_full,
    p.name as project_product_name,
    COUNT(CASE WHEN al.state = 'ALARM' AND al.severity = 'Critical' THEN 1 END) as critical_alarms,
    COUNT(CASE WHEN al.state = 'ALARM' AND al.severity = 'High' THEN 1 END) as high_alarms,
    COUNT(CASE WHEN al.state = 'ALARM' AND al.severity = 'Medium' THEN 1 END) as medium_alarms,
    COUNT(CASE WHEN al.state = 'ALARM' AND al.severity = 'Low' THEN 1 END) as low_alarms,
    COUNT(DISTINCT CASE WHEN inc.status IN ('OPEN', 'INVESTIGATING') THEN inc.id END) as active_incidents,
    COUNT(DISTINCT CASE WHEN can.status IN ('ERROR', 'NOT_RUNNING') THEN can.id END) as canary_failures,
    COALESCE(SUM(DISTINCT es.occurrence_count), 0) as total_errors
FROM
    accounts acc
    LEFT JOIN alarms al ON acc.id = al.account_id
    LEFT JOIN incidents inc ON acc.id = inc.account_id
    LEFT JOIN canaries can ON acc.id = can.account_id
    LEFT JOIN error_summaries es ON acc.id = es.account_id
        AND es.collection_date = CURRENT_DATE
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON acc.id = pa.account_id
    LEFT JOIN products p ON pa.product_id = p.id
GROUP BY
    acc.id, acc.account_id, acc.region, acc.account_name, acc.account_type,
    acc.category, acc.account_status, acc.partner_name, acc.customer_name,
    p.name;


--49. Canary status view (auto-populated from real Synthetics data)
-- Backs the dashboard "canary_status" dataset. One row per canary, joined to its
-- latest run and its owning system (product). Replaces the previously hand-seeded
-- canary_status table so the availability tiles reflect real collected data.
CREATE OR REPLACE VIEW canary_status AS
SELECT
    c.id                                            AS id,
    c.canary_name                                   AS canary_name,
    a.account_id                                    AS account_id,
    p.name                                          AS system_name,
    lr.run_status                                   AS last_run_status,
    lr.run_at                                       AS last_run_time,
    c.success_percentage                            AS success_percent,
    lr.duration_ms                                  AS avg_duration_ms,
    c.status                                         AS state,
    c.failure_reason                                AS failure_reason,
    c.endpoint_url                                  AS user_journey_description,
    c.updated_at                                    AS updated_at
FROM
    canaries c
    JOIN accounts a ON a.id = c.account_id
    LEFT JOIN (
        SELECT DISTINCT ON (account_id) account_id, product_id
        FROM product_accounts
        ORDER BY account_id, id
    ) pa ON pa.account_id = c.account_id
    LEFT JOIN products p ON p.id = pa.product_id
    LEFT JOIN LATERAL (
        SELECT run_status, run_at, duration_ms
        FROM canary_runs cr
        WHERE cr.canary_id = c.id
        ORDER BY cr.run_at DESC
        LIMIT 1
    ) lr ON TRUE;

--50. System health overview (auto-populated composite per-system health rollup)
-- Backs the dashboard "system_health_overview" dataset that drives the Overview
-- sheet health-score cards. One row per system (product), computed live from the
-- real collected data: alarms, security findings, canaries, and cost. Replaces the
-- previously hand-seeded system_health_overview table.
--
-- health_percentage is a weighted composite of:
--   * alarm health      (share of monitored alarms not in ALARM state)
--   * security health   (penalised by critical/high/medium findings)
--   * canary health     (share of canaries passing their latest run)
-- total_checks / passing_checks express the same as an absolute count so the
-- dashboard can show "N/M" style labels.
CREATE OR REPLACE VIEW system_health_overview AS
WITH sys AS (
    -- One system (product) per row, with the set of account ids that belong to it
    SELECT
        p.id                        AS product_id,
        p.name                      AS system_name,
        MIN(a.account_id)           AS account_id,   -- representative account for the system
        ARRAY_AGG(DISTINCT a.id)    AS account_pks
    FROM products p
    JOIN product_accounts pa ON pa.product_id = p.id
    JOIN accounts a ON a.id = pa.account_id
    GROUP BY p.id, p.name
),
alarm_agg AS (
    SELECT pa.product_id,
        COUNT(*)                                                          AS alarm_total,
        COUNT(*) FILTER (WHERE al.state = 'OK')                           AS alarm_ok,
        COUNT(*) FILTER (WHERE al.state = 'ALARM' AND al.severity IN ('Medium','Low')) AS alarm_warning,
        COUNT(*) FILTER (WHERE al.state = 'ALARM' AND al.severity IN ('Critical','High')) AS alarm_critical
    FROM alarms al
    JOIN product_accounts pa ON pa.account_id = al.account_id
    GROUP BY pa.product_id
),
sec_agg AS (
    SELECT pa.product_id,
        COALESCE(SUM(s.critical_count),0) AS security_findings_critical,
        COALESCE(SUM(s.high_count),0)     AS security_findings_high,
        COALESCE(SUM(s.medium_count),0)   AS security_findings_medium
    FROM security s
    JOIN product_accounts pa ON pa.account_id = s.account_id
    GROUP BY pa.product_id
),
canary_agg AS (
    SELECT pa.product_id,
        COUNT(*)                                        AS canary_total,
        COUNT(*) FILTER (WHERE c.status = 'RUNNING' AND COALESCE(c.success_percentage,0) >= 100) AS canary_passing
    FROM canaries c
    JOIN product_accounts pa ON pa.account_id = c.account_id
    GROUP BY pa.product_id
),
res_agg AS (
    SELECT pa.product_id,
        COUNT(*)                                              AS resource_total,
        COUNT(*) FILTER (WHERE sr.state IN ('running','available','active','Online')) AS resource_healthy
    FROM service_resources sr
    JOIN product_accounts pa ON pa.account_id = sr.account_id
    GROUP BY pa.product_id
),
cost_agg AS (
    -- latest monthly cost per account, summed to the system
    SELECT pa.product_id,
        COALESCE(SUM(cr.current_period_cost),0)                                       AS monthly_cost,
        CASE WHEN AVG(cr.cost_difference_percentage) > 0 THEN 'up'
             WHEN AVG(cr.cost_difference_percentage) < 0 THEN 'down'
             ELSE 'flat' END                                                          AS cost_trend
    FROM (
        SELECT DISTINCT ON (account_id) account_id, current_period_cost, cost_difference_percentage
        FROM cost_reports
        WHERE period_granularity = 'MONTHLY'
        ORDER BY account_id, period_end DESC
    ) cr
    JOIN product_accounts pa ON pa.account_id = cr.account_id
    GROUP BY pa.product_id
)
SELECT
    sys.product_id                                              AS id,
    sys.system_name                                             AS system_name,
    sys.account_id                                              AS account_id,
    -- total_checks = every discrete signal we evaluate; passing_checks = the healthy ones
    (COALESCE(aa.alarm_total,0) + COALESCE(ca.canary_total,0) + COALESCE(ra.resource_total,0)) AS total_checks,
    (COALESCE(aa.alarm_ok,0) + COALESCE(ca.canary_passing,0) + COALESCE(ra.resource_healthy,0)) AS passing_checks,
    -- weighted composite health percentage (0-100), robust to missing categories
    ROUND(
        100.0 * (
              0.5 * (CASE WHEN COALESCE(aa.alarm_total,0) = 0 THEN 1
                          ELSE COALESCE(aa.alarm_ok,0)::numeric / aa.alarm_total END)
            + 0.3 * (CASE WHEN (COALESCE(sa.security_findings_critical,0)
                                 + COALESCE(sa.security_findings_high,0)
                                 + COALESCE(sa.security_findings_medium,0)) = 0 THEN 1
                          ELSE GREATEST(0, 1 - (
                                 (3*COALESCE(sa.security_findings_critical,0)
                                 + 2*COALESCE(sa.security_findings_high,0)
                                 + COALESCE(sa.security_findings_medium,0))::numeric
                                 / NULLIF(10 * GREATEST(1, array_length(sys.account_pks,1)),0))) END)
            + 0.2 * (CASE WHEN COALESCE(ca.canary_total,0) = 0 THEN 1
                          ELSE COALESCE(ca.canary_passing,0)::numeric / ca.canary_total END)
        ), 1)                                                   AS health_percentage,
    COALESCE(aa.alarm_total,0)                                  AS alarm_total,
    COALESCE(aa.alarm_ok,0)                                     AS alarm_ok,
    COALESCE(aa.alarm_warning,0)                                AS alarm_warning,
    COALESCE(aa.alarm_critical,0)                               AS alarm_critical,
    COALESCE(sa.security_findings_critical,0)                   AS security_findings_critical,
    COALESCE(sa.security_findings_high,0)                       AS security_findings_high,
    COALESCE(sa.security_findings_medium,0)                     AS security_findings_medium,
    COALESCE(ra.resource_total,0)                               AS resource_total,
    COALESCE(ra.resource_healthy,0)                             AS resource_healthy,
    -- performance signal is derived from resources for now (no separate perf table)
    COALESCE(ra.resource_total,0)                               AS performance_total,
    COALESCE(ra.resource_healthy,0)                             AS performance_healthy,
    COALESCE(co.monthly_cost,0)                                 AS monthly_cost,
    COALESCE(co.cost_trend,'flat')                              AS cost_trend,
    NOW()                                                       AS last_updated,
    COALESCE(ca.canary_total,0)                                 AS canary_total,
    COALESCE(ca.canary_passing,0)                               AS canary_passing
FROM sys
    LEFT JOIN alarm_agg  aa ON aa.product_id = sys.product_id
    LEFT JOIN sec_agg    sa ON sa.product_id = sys.product_id
    LEFT JOIN canary_agg ca ON ca.product_id = sys.product_id
    LEFT JOIN res_agg    ra ON ra.product_id = sys.product_id
    LEFT JOIN cost_agg   co ON co.product_id = sys.product_id;
