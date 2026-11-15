"""
Opportunity generator — 3,000 opportunities.

Only converted leads (status = CONVERTED) with an assigned rep can be
converted to an opportunity. Opportunity lifecycle:
  stage → discovery → qualification → proposal → negotiation → closed
  status → open | won | lost

Won opportunities get closed_at + won_reason.
Lost opportunities get closed_at + lost_reason.
Open opportunities have closed_at = NULL.

StageHistory rows are written for every stage the opportunity traversed.
"""
from __future__ import annotations

from datetime import timedelta

from faker import Faker

from backend.app.data_generator.utils import weighted_choice
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.ids import SEQ_OPP
from backend.app.models.enums import (
    LeadStatus,
    LostReason,
    OpportunityStage,
    OpportunityStatus,
    ProductTier,
)
from backend.app.models.marketing import Lead
from backend.app.models.organization import Product, SalesRep
from backend.app.models.sales_ops import Opportunity, StageHistory


_STAGE_ORDER = [
    OpportunityStage.DISCOVERY,
    OpportunityStage.QUALIFICATION,
    OpportunityStage.PROPOSAL,
    OpportunityStage.NEGOTIATION,
    OpportunityStage.CLOSED,
]


def _pick_outcome(fake: Faker) -> OpportunityStatus:
    statuses = list(cfg.OUTCOME_WEIGHTS.keys())
    weights = [cfg.OUTCOME_WEIGHTS[s] for s in statuses]
    return OpportunityStatus(weighted_choice(fake, statuses, weights))


def _pick_lost_reason(fake: Faker) -> LostReason:
    reasons = list(cfg.LOST_REASON_WEIGHTS.keys())
    weights = [cfg.LOST_REASON_WEIGHTS[r] for r in reasons]
    return LostReason(weighted_choice(fake, reasons, weights))


def _pick_amount(fake: Faker, tier: ProductTier) -> int:
    lo, hi = cfg.OPPORTUNITY_AMOUNT_RANGES[tier.value]
    return fake.random_int(min=lo, max=hi)


def _stages_traversed(fake: Faker, status: OpportunityStatus) -> list[OpportunityStage]:
    """How far did this opp get before closing (or reaching open state)?"""
    if status == OpportunityStatus.OPEN:
        # Pick where it sits right now
        stages = list(cfg.OPEN_STAGE_WEIGHTS.keys())
        weights = [cfg.OPEN_STAGE_WEIGHTS[s] for s in stages]
        final = OpportunityStage(weighted_choice(fake, stages, weights))
        return _STAGE_ORDER[: _STAGE_ORDER.index(final) + 1]
    # WON or LOST always traversed all stages up to CLOSED
    return _STAGE_ORDER


def generate_opportunities(
    db: Session,
    leads: list[Lead],
    products: list[Product],
    sales_reps: list[SalesRep],
    seed: int,
    target_count: int,
) -> tuple[list[Opportunity], list[StageHistory]]:
    fake = Faker()
    Faker.seed(seed + 9)

    # Only converted leads are eligible
    converted_leads = [
        l for l in leads
        if l.status == LeadStatus.CONVERTED
        and l.assigned_rep_id is not None
        and l.converted_at is not None
    ]
    if len(converted_leads) < target_count:
        # If not enough, cap at what we have
        target_count = len(converted_leads)
    eligible = fake.random_elements(elements=converted_leads, length=target_count, unique=True)

    tier_by_code = {p.code: p.tier for p in products}
    rep_ids = {r.id for r in sales_reps}

    opportunities: list[Opportunity] = []
    stage_history: list[StageHistory] = []

    for lead in eligible:
        # Pick product interest → tier for amount range
        code_list = [c for c in lead.product_interest.split(",") if c]
        primary_code = code_list[0] if code_list else "PRD-0001"
        tier = tier_by_code.get(primary_code, ProductTier.BASIC)
        amount = _pick_amount(fake, tier)

        status = _pick_outcome(fake)
        stages = _stages_traversed(fake, status)
        final_stage = stages[-1]
        current_stage = final_stage

        converted_at = lead.converted_at
        opp_name = f"{lead.business_id} → {tier.value.title()} plan"

        if status == OpportunityStatus.WON:
            closed_at = converted_at + timedelta(days=fake.random_int(min=14, max=cfg.OPPORTUNITY_WINDOW_DAYS))
            won_reason = fake.random_element(elements=[
                "Best price", "Fastest implementation", "Strongest references",
                "Champion internally endorsed",
            ])
            lost_reason = None
        elif status == OpportunityStatus.LOST:
            closed_at = converted_at + timedelta(days=fake.random_int(min=14, max=cfg.OPPORTUNITY_WINDOW_DAYS))
            won_reason = None
            lost_reason = _pick_lost_reason(fake)
        else:  # OPEN
            closed_at = None
            won_reason = None
            lost_reason = None

        # Guard: rep must exist (defensive)
        if lead.assigned_rep_id not in rep_ids:
            continue

        opp = Opportunity(
            business_id=SEQ_OPP.next(),
            lead_id=lead.id,
            rep_id=lead.assigned_rep_id,
            name=opp_name,
            amount_usd=amount,
            stage=current_stage,
            status=status,
            expected_close_date=(
                converted_at + timedelta(days=90) if status == OpportunityStatus.OPEN else None
            ),
            closed_at=closed_at,
            won_reason=won_reason,
            lost_reason=lost_reason,
            created_at=converted_at,
            updated_at=closed_at or converted_at,
        )
        opportunities.append(opp)

        # Flush this opp so opp.id is populated before StageHistory references it
        db.add(opp)
        db.flush()

        # Stage history — one row per traversed stage (starting with creation)
        current_time = converted_at
        prev_stage = None
        for stg in stages:
            stage_history.append(
                StageHistory(
                    opportunity_id=opp.id,
                    from_stage=prev_stage,
                    to_stage=stg,
                    transitioned_at=current_time,
                    actor="system:data_generator",
                    notes=None,
                )
            )
            prev_stage = stg
            current_time = current_time + timedelta(days=fake.random_int(min=3, max=30))

    db.add_all(opportunities)
    db.flush()
    db.add_all(stage_history)
    db.flush()
    return opportunities, stage_history
