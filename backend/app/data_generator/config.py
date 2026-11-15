"""
Data generator configuration — volumes, distributions, weights.

All values are deterministic (seed 20261022). Changing this file changes the
output; existing reproducibility checksums will fail (by design — this is
the source of truth for dataset shape).
"""
from dataclasses import dataclass


DEFAULT_SEED = 20261022

# --- Volumes (baseline) ---
@dataclass(frozen=True)
class Volumes:
    companies: int = 5000
    contacts: int = 10000           # ~2 per company
    users: int = 50                 # mixed roles
    territories: int = 4            # NA, EMEA, APAC, LATAM
    products: int = 6               # 2 per tier (basic/pro/enterprise)
    sales_reps: int = 80            # ~20 per territory
    campaigns: int = 20
    leads: int = 20000
    activities_per_lead_min: int = 2
    activities_per_lead_max: int = 8
    opportunities: int = 3000       # ~15% of leads convert
    duplicate_groups: int = 500


STARTER_VOLUMES = Volumes(
    companies=50,
    contacts=100,
    users=10,
    territories=4,
    products=6,
    sales_reps=8,
    campaigns=5,
    leads=200,
    activities_per_lead_min=2,
    activities_per_lead_max=5,
    opportunities=30,
    duplicate_groups=5,
)

FULL_VOLUMES = Volumes()


# --- Distributions (must sum to 1.0 unless noted) ---

# Lead source distribution — ~60% from campaigns, 40% outbound/inbound
LEAD_SOURCE_WEIGHTS: dict[str, float] = {
    "webinar": 0.20,
    "content_download": 0.25,
    "paid_ad": 0.15,
    "event": 0.10,
    "partner_referral": 0.10,
    "outbound": 0.12,
    "inbound_form": 0.08,
}

# Campaign status distribution at data-gen time
CAMPAIGN_STATUS_WEIGHTS: dict[str, float] = {
    "active": 0.40,
    "completed": 0.35,
    "paused": 0.10,
    "draft": 0.10,
    "archived": 0.05,
}

# Industry distribution for companies
INDUSTRY_WEIGHTS: dict[str, float] = {
    "saas": 0.25,
    "fintech": 0.15,
    "healthcare": 0.15,
    "retail": 0.12,
    "manufacturing": 0.10,
    "logistics": 0.08,
    "education": 0.08,
    "other": 0.07,
}

# Region distribution for companies (drives territory)
REGION_WEIGHTS: dict[str, float] = {
    "north_america": 0.45,
    "emea": 0.30,
    "apac": 0.15,
    "latam": 0.10,
}

# Score category distribution — target ~15% hot, ~25% warm, ~35% nurture, ~25% cold
TARGET_SCORE_DISTRIBUTION: dict[str, float] = {
    "hot": 0.15,
    "warm": 0.25,
    "nurture": 0.35,
    "cold": 0.25,
}

# Conversion rate by score category (drives opportunity creation)
CONVERSION_RATE_BY_SCORE: dict[str, float] = {
    "hot": 0.55,
    "warm": 0.25,
    "nurture": 0.08,
    "cold": 0.02,
}

# Consent distribution — ~5% opted out of email, ~3% of marketing, etc.
CONSENT_GRANTED_RATES: dict[str, float] = {
    "email": 0.95,
    "phone": 0.88,
    "sms": 0.75,
    "marketing": 0.90,
}

# Opportunity stage distribution for OPEN opportunities
OPEN_STAGE_WEIGHTS: dict[str, float] = {
    "discovery": 0.35,
    "qualification": 0.30,
    "proposal": 0.20,
    "negotiation": 0.15,
}

# Opportunity outcome distribution (of converted opportunities)
OUTCOME_WEIGHTS: dict[str, float] = {
    "open": 0.55,
    "won": 0.25,
    "lost": 0.20,
}

# Lost reason distribution (given LOST outcome)
LOST_REASON_WEIGHTS: dict[str, float] = {
    "price": 0.30,
    "timing": 0.20,
    "competitor": 0.25,
    "no_budget": 0.15,
    "no_response": 0.05,
    "other": 0.05,
}

# Opportunity amount ranges by product tier (USD)
OPPORTUNITY_AMOUNT_RANGES: dict[str, tuple[int, int]] = {
    "basic": (500, 5000),
    "pro": (5000, 25000),
    "enterprise": (25000, 250000),
}

# --- Scoring rules (must match ScoreRule v1 defaults) ---
SCORE_RULE_V1 = {
    "version": "v1",
    "fit_weight": 30,
    "intent_weight": 35,
    "engagement_weight": 25,
    "recency_weight": 10,
    "hot_threshold": 80,
    "warm_threshold": 60,
    "nurture_threshold": 40,
}

# --- Sales rep workload capacity ---
SALES_REP_CAPACITY_RANGE = (30, 60)  # per rep, uniform int

# --- Time windows (UTC) ---
LEAD_CREATION_WINDOW_DAYS = 365      # leads created over last 12 months
ACTIVITY_WINDOW_DAYS = 30            # activities within 30 days of lead creation
OPPORTUNITY_WINDOW_DAYS = 180        # opps close within 6 months
TASK_SLA_HOURS = {                   # per U2
    "hot": 1,
    "warm": 24,
    "nurture": 72,
    "cold": 0,
}

# --- Anomaly injection ---
# Exactly one of each type is injected into baseline=False records.
ANOMALY_TYPES = [
    "optout_contacted",           # task created despite consent revoked
    "post_conversion_scoring",    # score_history includes post-converted activity
    "territory_mismatch",         # assigned rep not in lead's territory
    "duplicate_opportunity",      # 2 opps for one lead (uniqueness violation)
    "stage_gap",                  # stage_history skips a stage
]
