# Roadmap / Future Scope

Ideas that are intentionally **out of scope for the current release** but worth pursuing.

## 1. Consolidate the Aurora schema and QuickSight datasets

**Observation.** The dashboard currently depends on ~20 QuickSight datasets backed by a
large number of Aurora tables and ~45 views. Each data category (cost, security, config,
inventory, certificates, KMS, WAF, secrets, canaries, alarms, etc.) has its own table(s)
and view(s). For a customer who just wants the dashboard, this is a lot of surface area to
understand and maintain, and it isn't obvious which tables feed which visuals.

**Goal.** Reduce and clarify the data layer so the mapping "visual → dataset → table" is
easy to follow, without changing what the dashboard shows.

**Possible approach (not yet implemented).**
- Audit which of the ~20 datasets are actually bound to visuals on the shipped sheets, and
  retire any that are unused.
- Introduce a small number of well-named, purpose-built **reporting views** (for example,
  one per dashboard sheet) that pre-join and pre-aggregate the underlying tables, and point
  each QuickSight dataset at exactly one such view.
- Keep the raw ingestion tables as the system of record; the consolidation happens in the
  view layer, so the sender/receiver/collector write paths do not change.
- Document the final "sheet → view → source tables" lineage in `sql/`.

**Why deferred.** This touches the schema, the SQL views, the receiver/collector write
paths, and every QuickSight dataset binding at once. Done carelessly it would break the
dashboard we ship today. It deserves its own change with dedicated testing against a live
deployment, rather than being bundled into the initial genericized release.

## 2. Optional CloudOps assistant add-on

An earlier internal build included a natural-language "CloudOps" assistant (Amazon Bedrock +
a Slack bridge) layered on top of this dashboard. It is intentionally **not** included in
this sample to keep the scope focused on multi-account observability and dashboards. It
could be re-introduced later as a clearly separated, optional add-on module.
