# LeadFlow — Known Limitations & Assumptions

This document provides an honest accounting of what is not built, what is mocked, and what requires further engineering before production deployment. This was compiled in response to a technical review.

## 1. Synthetic Data & Business Metrics

- **Correlated Data Generation:** The synthetic data generator intentionally correlates scoring signals (activities) with conversion outcomes. Therefore, the "23x lift" and "$39.8M won revenue" are **workflow illustrations, not predictive evidence**. See `analytics/evaluate_scoring.py` for the proper methodology.
- **Timestamps:** While Faker seeds are fixed, generation times use `datetime.now()`. Byte-for-byte reproducibility across runs is not guaranteed (row counts are).
- **Currency:** All monetary values are assumed USD.

## 2. Anomaly Detection

- **Registry vs. Detector:** The Exception Center currently displays records written at injection time by the generator. It does not independently discover unknown anomalies. An independent detector suite is planned but not implemented.
- **Validation Engine Scope:** Several checks in `validator.py` explicitly exclude `is_baseline=False`. Therefore, the 19/19 checks pass because they ignore the injected anomalies.

## 3. Security & Authorization

- **RBAC Completeness:** `require_role()` is implemented, but most endpoints only use `get_current_user()`. A sales rep can currently query all leads, not just their own.
- **JWT Configuration:** The default secret in `config.py` (`change-me...`) will start in production if not overridden. No rate limiting is applied to `/login`.
- **Demo Credentials:** The password `leadflow-demo` is hardcoded in the seed and README.

## 4. Operational Readiness

- **Database Migrations:** Alembic is in `requirements.txt`, but no migration scripts exist. The app uses `Base.metadata.create_all()`.
- **Startup Resilience:** If auto-seeding fails during startup, the backend logs the error but continues running in a degraded state.
- **Task Completion:** There is no endpoint to mark a task as completed. SLA compliance will always read 0%.

## 5. Data Model & Workload

- **Workload Initialization:** The generator sets `sales_reps.current_workload = 0`, even when creating historical assignments. The routing engine may think a rep is empty when they already own leads.
- **Territory Matching:** Baseline generation randomly assigns reps, sometimes violating territory constraints. This makes the injected `territory_mismatch` anomaly less distinct.
- **Duplicate Prospects:** Opportunity uniqueness is enforced per `lead_id`, not per prospect (contact+company). Two leads can create duplicate pipeline.