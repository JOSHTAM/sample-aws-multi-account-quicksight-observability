# Overview Page: How Every Metric Is Calculated (and How to Change It)

This guide documents exactly how each tile on the QuickSight **Overview** page is
computed, where the numbers come from, and the step-by-step way to reconfigure
each one for your own organisation. Everything here is designed to be
**self-serve**: the health score, the status bands, the colours, and the icons
are all defined in two places you own — one SQL view and one QuickSight analysis.

> **TL;DR** — The health score is a transparent deduction: every system starts at
> **100** and loses a fixed, documented number of points for each real problem
> currently observed (firing alarms, security findings, failing canaries). You can
> always reconstruct the score from the tiles, and you can retune every number
> without touching application code.

---

## 1. The Overview card at a glance

Each system on the Overview page is shown as a card with these tiles:

| Tile | Example | What it means |
|---|---|---|
| **Health Score** | `58` (amber) | 0–100 composite. 100 = no active problems. Colour reflects the status band. |
| **Health Score Label** | `Degraded` | Plain-language band: **Healthy / Degraded / Unhealthy**. |
| **Health Status Icon** | `●●●○○` | 5-dot visual of the same score, for quick scanning. |
| **Service Availability** | `🟢 3/3 UP` | Canary (synthetic monitoring) pass rate for the system. |
| **Critical Alarms** | `🟢 Clear` | CloudWatch alarms currently **firing** (in `ALARM` state), plus any CRITICAL security findings. |
| **Warnings** | `🟡 3 HIGH` | Highest-priority non-critical attention item (see §5). |

All tiles read from a single dataset, **`system_health_overview`**, which is a SQL
**view** (not a table — nothing is hand-populated). The view is defined in
[`sql/schema/core-view.sql`](../../sql/schema/core-view.sql), view **#50**.

---

## 2. The Health Score model (penalty-based)

We deliberately **do not** use an opaque weighted average. Instead the score is a
**deduction model**:

```
health_percentage = GREATEST(0, 100
     − PENALTY_ALARM_FIRING     × (number of CloudWatch alarms in ALARM state)
     − PENALTY_FINDING_CRITICAL × (number of CRITICAL security findings)
     − PENALTY_FINDING_HIGH     × (number of HIGH security findings)
     − PENALTY_FINDING_MEDIUM   × (number of MEDIUM security findings)
     − PENALTY_CANARY_DOWN      × (number of canaries failing their latest run))
```

### Default penalty values

These live as named constants in the `weights` CTE at the top of the
`system_health_overview` view:

| Constant | Default | Applied to |
|---|---|---|
| `penalty_alarm_firing` | **20** | each CloudWatch alarm in `ALARM` state |
| `penalty_finding_critical` | **20** | each CRITICAL security finding |
| `penalty_finding_high` | **5** | each HIGH security finding |
| `penalty_finding_medium` | **1** | each MEDIUM security finding |
| `penalty_canary_down` | **20** | each canary failing its latest run |

**How the defaults were calibrated:** the three "something is actually wrong right
now" signals — a firing alarm, a critical finding, and a down canary — each cost
**20**, so any single real operational problem moves a system at least one band
toward attention, and it takes a genuine cluster of problems to reach red
(< 70). High and medium security findings accrue more gently (**5** and **1**)
because they are triage backlog, not live outages. Tune these to match your own
risk appetite.

### Worked example

A system with **0 firing alarms, 0 critical findings, 3 HIGH findings, 9 MEDIUM
findings, and no failing canaries**:

```
100 − (5 × 3) − (1 × 9) = 100 − 15 − 9 = 76  →  "Degraded" (amber)
```

The score of 76 is fully explainable from the Warnings tile ("3 HIGH") and the
security detail — no hidden weighting. The system is operational (nothing firing,
no outage), so it reads amber "Degraded" rather than red — red is reserved for
systems with live problems.

### Why these signals (and not others)

- **Alarm state is authoritative.** CloudWatch alarms have **no native
  "severity"** attribute — the collector never sends one, so the loader defaults
  every alarm to `Medium`. Any severity-based split of alarms would therefore be
  fiction. We use the real signal: the alarm **state**.
  - `ALARM` → actively firing → penalised, and shown in **Critical Alarms**.
  - `INSUFFICIENT_DATA` → not enough data to judge (new or low-traffic alarms).
    **Not penalised** — this is a monitoring-coverage nudge, not a failure. Shown
    in **Warnings** as `NO DATA`.
  - `OK` → healthy.
- **Security finding severities are real.** They come straight from Security Hub /
  GuardDuty / Inspector `Severity.Label`, aggregated to
  `critical_count / high_count / medium_count`. So they drive graded penalties.
- **Canary pass/fail is real** (CloudWatch Synthetics).
- **Resource inventory is deliberately excluded from the score.** The count of
  buckets, functions, and subnets is *inventory*, not *health*. Including it (the
  old behaviour) produced a misleading "13/226" and dragged the score down for no
  operational reason. Inventory is still available on the detail sheets via
  `resource_total` / `resource_healthy`.

### If a category has no data

Missing categories simply contribute **no penalty**. A system with nothing wrong
(or nothing yet collected) scores **100**. There is no divide-by-zero and no
artificial deflation.

---

## 3. Status bands, colours, and the 5-dot icon

The score maps to three bands. The band cut-offs are defined in **three matching
places**, all of which you control:

| Band | Score | Health Score colour | Label word | 5-dot icon |
|---|---|---|---|---|
| **Healthy** | ≥ 90 | green `#2CAD00` | `Healthy` | `●●●●●` (≥90), `●●●●○` (≥75) |
| **Degraded** | 70–89 | amber `#FFB500` | `Degraded` | `●●●○○` (≥60) |
| **Unhealthy** | < 70 | red `#DE3B00` | `Unhealthy` | `●●○○○` (≥40), `●○○○○` (<40) |

The three cut-offs (**90** and **70**) are the "story" thresholds; the 5-dot icon
adds finer intermediate marks (90/75/60/40) purely for visual granularity.

---

## 4. Tile-by-tile reference

For each tile: the field it reads, how that field is computed in SQL, and any
presentation logic in the analysis.

### Health Score
- **Reads:** `system_health_overview.health_percentage` (aggregated `SUM`; each
  card is filtered to one system so `SUM` = that system's value).
- **SQL:** penalty model in view #50 (§2).
- **Presentation:** KPI conditional-formatting colour bands (green/amber/red) at
  the 90/70 cut-offs.

### Health Score Label
- **Reads:** calculated field `health_score_label`.
- **Logic:** `ifelse(health_percentage >= 90, "Healthy", >= 70, "Degraded", "Unhealthy")`.

### Health Status Icon
- **Reads:** calculated field `health_status_icon`.
- **Logic:** `ifelse(health_percentage >= 90 "●●●●●", >= 75 "●●●●○", >= 60 "●●●○○", >= 40 "●●○○○", "●○○○○")`.

### Service Availability
- **Reads:** calculated field `service_availability`, from `canary_passing` and `canary_total`.
- **SQL:** `canary_total` = number of canaries for the system; `canary_passing` =
  canaries with `status = 'RUNNING' AND success_percentage >= 100`.
- **Logic:** all passing → `🟢 P/T UP`; some passing → `🟡 P/T DEGRADED`; none → `🔴 0/T`.
- **`0/0 UP`** means the system has no canaries configured yet — add canaries to
  populate it (see [onboarding-a-new-system.md](../onboarding-a-new-system.md)).

### Critical Alarms
- **Reads:** calculated field `alert_line_1`, from `alarm_critical` and `security_findings_critical`.
- **SQL:** `alarm_critical` = count of CloudWatch alarms currently in **`ALARM`**
  state (this is *not* a severity split — see §2).
- **Logic:** firing alarms → `🔴 N CRIT`; else critical findings → `🔴 N CRIT`;
  else `🟢 Clear`.

### Warnings
- **Reads:** calculated field `alert_line_2`, from `security_findings_high`,
  `security_findings_medium`, and `alarm_warning`.
- **SQL:** `security_findings_high` / `_medium` from `security` counts;
  `alarm_warning` = count of alarms in **`INSUFFICIENT_DATA`** state.
- **Logic (priority order):** HIGH findings → `🟡 N HIGH`; else MEDIUM findings →
  `🟡 N MED`; else insufficient-data alarms → `🟡 N NO DATA`; else `-`.

---

## 5. How to reconfigure each metric (step-by-step)

There are exactly **two** files to edit. Nothing else.

### A. Change the score weighting (penalties)

1. Open [`sql/schema/core-view.sql`](../../sql/schema/core-view.sql) and find the
   `system_health_overview` view (view #50), then the `weights` CTE at the top.
2. Change any penalty value, e.g. make a firing alarm cost more:
   ```sql
   WITH weights AS (
       SELECT
           30::numeric AS penalty_alarm_firing,      -- was 20
           20::numeric AS penalty_finding_critical,
            5::numeric AS penalty_finding_high,
            1::numeric AS penalty_finding_medium,
           20::numeric AS penalty_canary_down
   )
   ```
3. Re-apply the view to your Aurora database (run the view statement via the RDS
   Data API, or re-run the schema load). The change takes effect on the next
   QuickSight dataset refresh — no redeploy of Lambdas or CloudFormation needed.

To add a **new** penalty category (e.g. penalise unresolved incidents): add a
constant to `weights`, add a `..._agg` CTE that counts the signal, and subtract
`w.<new_penalty> * COALESCE(<count>, 0)` in the `health_percentage` expression.

### B. Change the status bands / colours / icon

The band cut-offs live in the QuickSight analysis. You can edit them either in the
QuickSight console (no code) or in the JSON (version-controlled).

**Option 1 — QuickSight console (easiest):**
1. Open the analysis → **Overview** sheet.
2. **Label word / icon dots:** edit the calculated fields `health_score_label` and
   `health_status_icon` (Data pane → Calculated fields). Change the numbers in the
   `ifelse(...)`.
3. **Health Score colour:** select each Health Score KPI → **Format visual** →
   **Conditional formatting**, and adjust the 70 / 90 breakpoints. *Note: this must
   be repeated on each system card, because each card is a separate KPI visual.*

**Option 2 — edit the JSON (keeps it in the repo):**
1. Edit the calculated-field expressions in
   [`quicksight/analysis-definition.json`](../analysis-definition.json) — search
   for `health_score_label`, `health_status_icon`, `alert_line_1`, `alert_line_2`.
2. Keep the same expressions in
   [`quicksight/quicksight-dashboard.template.json`](../quicksight-dashboard.template.json)
   and in the shipped bundle
   [`quicksuite/A360-Sample-Template.qs`](../../quicksuite/A360-Sample-Template.qs)
   (the `.qs` is a ZIP; the analysis JSON is under `analysis/`). All three must
   match so a fresh import and a live analysis stay consistent.
3. Re-import via the QuickSight migration stack (see the QuickSight deployment
   steps in [../deployment-guide.md](../deployment-guide.md)).

### C. Change what counts as a "firing" alarm or a "passing" canary

- **Alarm state mapping** (which states are critical / warning / OK): `alarm_agg`
  CTE in view #50.
- **Canary "passing" rule** (`RUNNING AND success_percentage >= 100`): `canary_agg`
  CTE in view #50.

---

## 6. Important notes and gotchas

- **Each Overview card is filtered to one system** and aggregates
  `health_percentage` with `SUM`. Because a card sees exactly one row, `SUM` equals
  that system's score. Do **not** point a single card at multiple systems, or the
  `SUM` will exceed 100 and break the colour logic.
- **Adding a new system** means pointing an Overview card at it (rename the title,
  re-point every tile's `system_name` filter) and duplicating the **System A** detail
  sheet — see [onboarding-a-new-system.md](../onboarding-a-new-system.md), especially
  [what auto-populates vs. what you configure](../onboarding-a-new-system.md#what-auto-populates-vs-what-you-configure-by-hand).
  The card titles ("System A" … "System F") are hard-coded rich text, not data-driven, and
  each tile carries its own `system_name` filter set to a placeholder value.
- **The colour bands are duplicated per card** in the JSON. If you change them in
  JSON, change every card; the console lets you do them one at a time.
- **No synthetic data.** Every field above is computed live from collected data.
  A brand-new deployment with nothing collected yet will legitimately show `100`,
  `Clear`, and `0/0 UP` until the first collection runs.

---

## 7. Data lineage summary

| Signal | Real source | Landed in | Used by |
|---|---|---|---|
| Alarm state | CloudWatch `DescribeAlarms` → `StateValue` | `alarms.state` | Critical Alarms, Warnings, score |
| Alarm severity | *(none — CloudWatch has no severity; defaulted to `Medium`, unused for scoring)* | `alarms.severity` | not used in score |
| Finding severity | Security Hub / GuardDuty / Inspector `Severity.Label` | `security.{critical,high,medium}_count` | Warnings, Critical Alarms, score |
| Canary result | CloudWatch Synthetics | `canaries.status`, `canaries.success_percentage`, `canary_runs` | Service Availability, score |
| Resource state | Service describe/list APIs | `service_resources.state` | detail sheets only (not score) |
| Cost | Cost Explorer | `cost_reports.current_period_cost` | cost tile |
