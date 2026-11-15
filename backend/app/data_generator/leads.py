"""
Lead generator — 20,000 baseline leads with realistic funnel distribution.

Each lead:
  - References a valid company + contact (contact.company_id == lead.company_id)
  - References a valid territory (matches company's territory)
  - Has a product_interest (1-3 products)
  - Has current_score + current_score_category (approximate — real scoring engine runs later)
  - Status distribution: ~60% new/scored, ~15% qualified, ~15% assigned/working, ~10% converted/disqualified

Scores here are PLACEHOLDERS — they reflect the target distribution so downstream
engines (routing, task-gen, opportunities) can work immediately. The real scoring
engine will OVERWRITE these via LeadScoreHistory for the demo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from faker import Faker

from backend.app.data_generator.utils import weighted_choice
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.ids import SEQ_LEAD
from backend.app.models.enums import (
    LeadSource,
    LeadStatus,
    ProductTier,
    ScoreCategory,
)
from backend.app.models.marketing import Campaign, Lead, LeadCampaign
from backend.app.models.organization import Company, Contact, Product, SalesRep, Territory


# Rough status weights by score category (baseline funnel)
_STATUS_BY_SCORE: dict[ScoreCategory, dict[LeadStatus, float]] = {
    ScoreCategory.HOT: {
        LeadStatus.NEW: 0.05, LeadStatus.SCORED: 0.05, LeadStatus.QUALIFIED: 0.15,
        LeadStatus.ASSIGNED: 0.15, LeadStatus.WORKING: 0.05, LeadStatus.CONVERTED: 0.55,
    },
    ScoreCategory.WARM: {
        LeadStatus.NEW: 0.10, LeadStatus.SCORED: 0.15, LeadStatus.QUALIFIED: 0.20,
        LeadStatus.ASSIGNED: 0.15, LeadStatus.WORKING: 0.10, LeadStatus.CONVERTED: 0.30,
    },
    ScoreCategory.NURTURE: {
        LeadStatus.NEW: 0.30, LeadStatus.SCORED: 0.30, LeadStatus.QUALIFIED: 0.20,
        LeadStatus.ASSIGNED: 0.10, LeadStatus.WORKING: 0.03, LeadStatus.CONVERTED: 0.05,
    },
    ScoreCategory.COLD: {
        LeadStatus.NEW: 0.55, LeadStatus.SCORED: 0.35, LeadStatus.DISQUALIFIED: 0.10,
    },
}


def _pick_score_category(fake: Faker) -> ScoreCategory:
    cats = list(cfg.TARGET_SCORE_DISTRIBUTION.keys())
    weights = [cfg.TARGET_SCORE_DISTRIBUTION[c] for c in cats]
    return ScoreCategory(weighted_choice(fake, cats, weights))


def _score_range_for(cat: ScoreCategory) -> tuple[int, int]:
    return {
        ScoreCategory.HOT: (80, 100),
        ScoreCategory.WARM: (60, 79),
        ScoreCategory.NURTURE: (40, 59),
        ScoreCategory.COLD: (0, 39),
    }[cat]


def _pick_status(fake: Faker, cat: ScoreCategory) -> LeadStatus:
    options = _STATUS_BY_SCORE[cat]
    statuses = list(options.keys())
    weights = list(options.values())
    return weighted_choice(fake, statuses, weights)


def _pick_source(fake: Faker) -> LeadSource:
    sources = list(cfg.LEAD_SOURCE_WEIGHTS.keys())
    weights = [cfg.LEAD_SOURCE_WEIGHTS[s] for s in sources]
    return LeadSource(weighted_choice(fake, sources, weights))


def _product_interest(fake: Faker, products: list[Product]) -> str:
    n = fake.random_int(min=1, max=3)
    chosen = fake.random_elements(elements=products, length=n, unique=True)
    return ",".join(p.code for p in chosen)


def generate_leads(
    db: Session,
    companies: list[Company],
    contacts: list[Contact],
    territories: list[Territory],
    products: list[Product],
    sales_reps: list[SalesRep],
    campaigns: list[Campaign],
    seed: int,
    count: int,
) -> list[Lead]:
    """20,000 leads with valid FKs and realistic funnel distribution."""
    fake = Faker()
    Faker.seed(seed + 3)

    # Index contacts by company
    contacts_by_company: dict[int, list[Contact]] = {}
    for c in contacts:
        contacts_by_company.setdefault(c.company_id, []).append(c)

    now = datetime.now(timezone.utc)
    window_days = cfg.LEAD_CREATION_WINDOW_DAYS

    leads: list[Lead] = []
    lead_campaign_links: list[LeadCampaign] = []

    for _ in range(count):
        company = fake.random_element(elements=companies)
        candidate_contacts = contacts_by_company.get(company.id, [])
        if not candidate_contacts:
            continue
        contact = fake.random_element(elements=candidate_contacts)

        cat = _pick_score_category(fake)
        lo, hi = _score_range_for(cat)
        score = fake.random_int(min=lo, max=hi)
        status = _pick_status(fake, cat)

        # Creation date within window
        created_at = now - timedelta(
            days=fake.random_int(min=0, max=window_days),
            hours=fake.random_int(min=0, max=23),
        )

        # Assignment for statuses that imply it
        assigned_rep_id = None
        assigned_at = None
        if status in (LeadStatus.ASSIGNED, LeadStatus.WORKING, LeadStatus.CONVERTED):
            rep = fake.random_element(elements=sales_reps)
            assigned_rep_id = rep.id
            assigned_at = created_at + timedelta(hours=fake.random_int(min=1, max=72))

        converted_at = None
        if status == LeadStatus.CONVERTED:
            converted_at = (assigned_at or created_at) + timedelta(
                days=fake.random_int(min=1, max=60)
            )

        lead = Lead(
            business_id=SEQ_LEAD.next(),
            contact_id=contact.id,
            company_id=company.id,
            source=_pick_source(fake),
            status=status,
            current_score=score,
            current_score_category=cat,
            current_score_version="v1",
            last_scored_at=created_at + timedelta(hours=fake.random_int(min=1, max=48)),
            assigned_rep_id=assigned_rep_id,
            assigned_at=assigned_at,
            converted_at=converted_at,
            is_duplicate=False,
            is_baseline=True,
            territory_id=company.territory_id,
            product_interest=_product_interest(fake, products),
            notes=None,
        )
        # Override created_at to realistic past date
        lead.created_at = created_at
        lead.updated_at = created_at
        leads.append(lead)

    db.add_all(leads)
    db.flush()

    # Lead → Campaign attribution (~60% of leads get 1 primary campaign)
    for lead in leads:
        if fake.boolean(chance_of_getting_true=60):
            campaign = fake.random_element(elements=campaigns)
            lead_campaign_links.append(
                LeadCampaign(
                    lead_id=lead.id,
                    campaign_id=campaign.id,
                    attributed_at=lead.created_at,
                    is_primary=True,
                )
            )
    db.add_all(lead_campaign_links)
    db.flush()

    return leads

