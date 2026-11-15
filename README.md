# LeadFlow — Lead Intelligence & Opportunity Management Platform

Enterprise lead scoring, routing, task automation, and opportunity management.

## Quick Start (Docker — one command)

```bash
docker compose up --build -d
```

Then open:
- **Frontend:** http://localhost:3003
- **API docs (Swagger):** http://localhost:8002/docs
- **Health:** http://localhost:8002/health

**Login:** Any seeded user (e.g. `laura.boone.46@leadflow-demo.io`) with password `leadflow-demo`. Click **"Use demo credentials"** on the login page.

## Local Development

### Prerequisites
- Python 3.12+
- Node 20+
- Docker & Docker Compose

### Setup

```bash
# 1. Start Postgres
docker compose up -d db

# 2. Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
./run-local.sh seed full     # generate 20k leads + 5 anomalies
./run-local.sh 8002          # boot API on :8002

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                  # boots on :3003
```

## Architecture

Three-tier:

```
┌─ Frontend (React 19 + TS + Tailwind + Recharts) ────┐
│  Dashboard · Leads · Lead Detail · Opportunities    │
│  Exceptions · Admin                                 │
└─────────────────┬───────────────────────────────────┘
                  │ REST (JWT)
┌─────────────────▼───────────────────────────────────┐
│  Backend (FastAPI + SQLAlchemy 2.0)                 │
│  Engines: scoring · routing · task · opportunity ·  │
│           analytics · validation · data generator   │
└─────────────────┬───────────────────────────────────┘
                  │ SQL
┌─────────────────▼───────────────────────────────────┐
│  PostgreSQL 16 — 21 tables, all constraints         │
└─────────────────────────────────────────────────────┘
```

## Business Rules

- **Scoring:** Fit (30) + Intent (35) + Engagement (25) + Recency (10) = 100. Hot ≥ 80, Warm ≥ 60, Nurture ≥ 40, Cold < 40. Versioned, configurable, explainable.
- **Consent (A1):** per-channel (email, phone, SMS, marketing). No task created if all channels revoked.
- **Routing:** territory + product match mandatory. Load-balanced by utilization. Deterministic tie-break by rep.id.
- **SLA (U2):** Hot 1h, Warm 24h, Nurture 72h, Cold none.
- **Opportunity uniqueness:** enforced by `UNIQUE(lead_id)`.
- **Lifecycle:** discovery → qualification → proposal → negotiation → closed. No skips, no reversals.

## Data Model (21 tables)

`roles`, `users`, `territories`, `products`, `sales_reps`, `campaigns`, `companies`, `contacts`, `leads`, `lead_campaigns`, `activities`, `consents`, `score_rules`, `lead_score_history`, `lead_assignment_history`, `tasks`, `opportunities`, `stage_history`, `duplicate_groups`, `exception_records`, `audit_log`.

## The 5 Injected Anomalies

1. **optout_contacted** (CRITICAL) — task created for opted-out lead
2. **post_conversion_scoring** (HIGH) — activity occurring after conversion
3. **territory_mismatch** (HIGH) — lead assigned to rep outside its territory
4. **duplicate_opportunity** (HIGH) — two opps for the same contact+company
5. **stage_gap** (MEDIUM) — stage history skips a stage

Ground truth: `data/ground_truth/ground_truth.csv`. Isolation is enforced — no engine reads it.

## Testing

```bash
# All unit tests
PYTHONPATH=. python3 -m pytest backend/tests/ -v

# Data validation
PYTHONPATH=. python3 -m backend.app.validation.validator
```

**46/46 tests pass.** Validation: 17/18 checks pass (1 fails on an injected anomaly, correct behavior).

## Business KPIs (live from 20k leads)

| Metric | Value |
|---|---|
| Leads | 20,000 |
| HOT leads | 1,520 (7.6%) |
| Conversion rate | 17.8% |
| Opportunities | 3,561 |
| Open pipeline | $91.3M |
| Won revenue | $39.8M |
| Win rate | 55.1% |
| Avg deal size | $44.9K |

**Scoring engine proof:** HOT converts at **54.5%** vs COLD at **2.3%** — a 23x lift.

## Commands

```bash
./run-local.sh                    # boot backend on :8002
./run-local.sh 8003               # custom port
./run-local.sh seed               # generate starter dataset
./run-local.sh seed full          # generate full dataset
./run-local.sh check              # verify DB state

cd frontend && npm run dev        # boot frontend on :3003
```

## Docker

```bash
docker compose up --build -d      # build + start all services
docker compose logs -f backend    # follow backend logs
docker compose down               # stop (keeps data)
docker compose down -v            # stop + wipe database
```