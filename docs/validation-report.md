# LeadFlow — Validation Report

Executed: `2026-11-15T10:37:58.709249+00:00`

- **Total checks:** 19
- **Passed:** 19
- **Failed:** 0
- **Critical failures:** 0
- **Warnings:** 0

## All Checks

| Result | Category | Check | Violations | Severity | Details |
|--------|----------|-------|------------|----------|---------|
| ✅ | integrity | fk_integrity | 0 | info | Orphaned foreign keys across leads/contacts/companies/tasks/opportunities |
| ✅ | scoring | score_bounds | 0 | info | Leads out of bounds (current): 0, history: 0 |
| ✅ | arithmetic | score_component_sum | 0 | info | Rows where fit+intent+engagement+recency != total |
| ✅ | lifecycle | opportunity_uniqueness | 0 | info | Leads with more than one opportunity (should be 0) |
| ✅ | lifecycle | opportunity_outcome_consistency | 0 | info | Opportunities with inconsistent won/lost/open fields |
| ✅ | lifecycle | stage_history_continuity | 0 | info | Opportunities with broken stage continuity |
| ✅ | consent | consent_compliance | 0 | info | Tasks created for leads with no granted consent channel |
| ✅ | consent | task_consent_snapshot | 0 | info | Baseline tasks with consent_eligible=False |
| ✅ | temporal | activity_temporal | 0 | info | Activities occurring before lead creation |
| ✅ | temporal | post_conversion_activity | 0 | info | Baseline activities occurring after conversion |
| ✅ | temporal | opportunity_temporal | 0 | info | Opportunities closed before creation |
| ✅ | lifecycle | converted_lead_has_opp | 0 | info | CONVERTED leads without an opportunity (conversion created but opp missing) |
| ✅ | integrity | rep_workload_bounds | 0 | info | Reps with workload outside [0, capacity] |
| ✅ | lifecycle | lead_status_consistency | 0 | info | CONVERTED w/o converted_at: 0, ASSIGNED w/o assigned_at: 0 |
| ✅ | scoring | score_history_rule_exists | 0 | info | Score history rows with unknown rule_version |
| ✅ | integrity | duplicate_contact_emails | 0 | info | Emails appearing more than once in contacts |
| ✅ | arithmetic | conversion_funnel_sanity | 0 | info | Conversion rate 17.79% — expected between 0.1% and 50% |
| ✅ | arithmetic | negative_amounts | 0 | info | Opportunities with negative amount |
| ✅ | integrity | orphaned_stage_history | 0 | info | Stage history rows with no parent opportunity |

## The 5 Injected Anomalies

| Anomaly | Severity | Detected |
|---------|----------|----------|
| post_conversion_scoring | — | ✅ |
| stage_gap | — | ✅ |
| territory_mismatch | — | ✅ |
| duplicate_opportunity | — | ✅ |
| optout_contacted | — | ✅ |