# LeadFlow — 5-Minute Demo Guide

**Target Audience:** Technical interviewers, hiring managers, stakeholders.
**Setup:** Backend on `:8002`, Frontend on `:3003`.

## 0:00 — Login
1. Open **http://localhost:3003**
2. Click **"Use demo credentials"**
3. Click **"Sign in"**

*Talking Point:* "This is LeadFlow. We're logging in as Laura, an admin. The platform has 20,000 synthetic leads, fully scored and routed."

## 0:30 — Executive Dashboard
*Walk through the KPIs.*
- **Total Leads:** 20,000
- **Revenue Won:** $39.8M
- **HOT vs COLD Conversion:** 54.5% vs 2.3%

*Talking Point:* "This is the executive view. Notice the scoring strategy table. HOT leads show a 54.5% conversion rate compared to COLD at 2.3%. *Caveat:* In this synthetic dataset, outcome is correlated with score category by design. For a real deployment, we'd need independent holdout data to prove predictive lift, which is documented in our evaluation methodology."

## 1:30 — Lead Management & Explainability
1. Click **Leads** in the sidebar.
2. Filter by Tier: **HOT**.
3. Click a lead's Business ID.

*Talking Point:* "Every lead is scored. But it's not a black box. Look at the Score Explanation. The lead scored an 86 because Fit is 30/30, Intent is 30/35, etc. We store 12 feature-level contributions so a rep knows exactly why they are calling this person."

## 2:30 — Routing & Consent
*Navigate back to Leads.*
*Talking Point:* "After scoring, leads are automatically routed to reps based on territory and product expertise, balanced by workload. Before a rep gets a task, the engine checks per-channel consent. If a prospect opted out of email and phone, we will not generate a contact task."

## 3:30 — Opportunity Lifecycle
1. Click **Opportunities**.
2. Show the pipeline stages (discovery → negotiation → closed).

*Talking Point:* "When a lead converts, an opportunity is created. The lifecycle is strictly forward-only. You cannot skip stages. And to close an opportunity, the API forces you to specify Won or Lost, and provide a reason. We block the generic 'advance' endpoint from setting a terminal state without an outcome."

## 4:30 — Exception Center
1. Click **Exceptions**.

*Talking Point:* "Data quality is critical. We inject 5 specific anomalies during generation: consent violations, stage gaps, territory mismatches, duplicate opportunities, and post-conversion scoring. We surface these in the Exception Center. Note: currently, these records are written at injection time, not by an independent background detector. That's a documented limitation and a clear next step for production."

