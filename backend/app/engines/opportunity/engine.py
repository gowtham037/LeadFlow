"""
Opportunity management engine.

Business rules:
  - One opportunity per lead (enforced by DB unique constraint)
  - Stage progression is STRICTLY forward: discovery → qualification → proposal
    → negotiation → closed. No skipping, no reversing.
  - Won requires closed_at set + lost_reason NULL
  - Lost requires closed_at set + lost_reason set (enum)
  - Every stage transition writes an immutable StageHistory row
  - Lifecycle transitions are validated (can't jump discovery → proposal)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.enums import (
    LeadStatus,
    LostReason,
    OpportunityStage,
    OpportunityStatus,
)
from backend.app.models.marketing import Lead
from backend.app.models.organization import Product
from backend.app.models.sales_ops import Opportunity, StageHistory


# Canonical stage order (must be traversed left-to-right)
STAGE_ORDER: list[OpportunityStage] = [
    OpportunityStage.DISCOVERY,
    OpportunityStage.QUALIFICATION,
    OpportunityStage.PROPOSAL,
    OpportunityStage.NEGOTIATION,
    OpportunityStage.CLOSED,
]


class InvalidStageTransition(Exception):
    """Raised when a stage transition violates the forward-only rule."""


class DuplicateOpportunity(Exception):
    """Raised when a lead already has an opportunity."""


@dataclass
class OpportunityCreated:
    opportunity: Opportunity
    stage_history: StageHistory


def _validate_forward_transition(
    from_stage: OpportunityStage,
    to_stage: OpportunityStage,
) -> None:
    """
    Enforce stage-by-stage progression.

    Rules:
      - Cannot move to the same or an earlier stage
      - Cannot SKIP stages (spec: stage gaps are anomalies)
      - Closing (to_stage=CLOSED) is allowed from any open stage
        (final transition to closed is a terminal event, not a skip)
    """
    if from_stage not in STAGE_ORDER or to_stage not in STAGE_ORDER:
        raise InvalidStageTransition(f"Unknown stage: {from_stage} → {to_stage}")

    from_idx = STAGE_ORDER.index(from_stage)
    to_idx = STAGE_ORDER.index(to_stage)

    if to_idx <= from_idx:
        raise InvalidStageTransition(
            f"Cannot move {from_stage.value} → {to_stage.value}: only forward transitions allowed"
        )

    # Closing (to CLOSED) is always allowed from any open stage — no skip rule
    if to_stage == OpportunityStage.CLOSED:
        return

    # Otherwise require adjacent step (no skipping)
    if to_idx != from_idx + 1:
        raise InvalidStageTransition(
            f"Cannot skip stages: {from_stage.value} → {to_stage.value} "
            f"(must go through {STAGE_ORDER[from_idx + 1].value})"
        )


def _pick_amount_for_lead(lead: Lead, db: Session) -> float:
    """Derive an initial amount from the lead's primary product interest list price."""
    codes = [c.strip() for c in (lead.product_interest or "").split(",") if c.strip()]
    if not codes:
        return 5000.0
    # Pick the highest-priced product as base — a prospect interested in
    # enterprise typically converts at the higher tier
    prods = db.query(Product).filter(Product.code.in_(codes)).all()
    if not prods:
        return 5000.0
    return float(max(p.list_price for p in prods))


def create_opportunity(
    db: Session,
    lead: Lead,
    name: str | None = None,
    amount_usd: float | None = None,
    as_of: datetime | None = None,
) -> OpportunityCreated:
    """
    Convert a qualified/converted lead to an opportunity.

    Preconditions:
      - Lead must have assigned_rep_id
      - Lead must have status in {QUALIFIED, ASSIGNED, WORKING, CONVERTED}
      - No existing opportunity for this lead

    On success:
      - Creates Opportunity at stage=DISCOVERY, status=OPEN
      - Writes StageHistory row (from_stage=NULL, to_stage=DISCOVERY)
      - If lead.status was QUALIFIED/ASSIGNED/WORKING, moves it to CONVERTED
      - Updates lead.converted_at

    Raises DuplicateOpportunity if the lead already has an opportunity.
    """
    if lead.assigned_rep_id is None:
        raise ValueError(f"Lead {lead.id} has no assigned rep")

    if lead.status not in (
        LeadStatus.QUALIFIED, LeadStatus.ASSIGNED,
        LeadStatus.WORKING, LeadStatus.CONVERTED,
    ):
        raise ValueError(
            f"Lead {lead.id} in status {lead.status.value} — not eligible for conversion"
        )

    existing = db.query(Opportunity).filter(Opportunity.lead_id == lead.id).one_or_none()
    if existing is not None:
        raise DuplicateOpportunity(
            f"Lead {lead.id} already has opportunity {existing.business_id}"
        )

    now = as_of or datetime.now(timezone.utc)

    opp_name = name or f"{lead.business_id} — opportunity"
    amount = amount_usd if amount_usd is not None else _pick_amount_for_lead(lead, db)

    # Generate next OPP business_id
    count = db.query(Opportunity).count()
    business_id = f"OPP-2026-{count + 1:06d}"

    opp = Opportunity(
        business_id=business_id,
        lead_id=lead.id,
        rep_id=lead.assigned_rep_id,
        name=opp_name,
        amount_usd=amount,
        stage=OpportunityStage.DISCOVERY,
        status=OpportunityStatus.OPEN,
        expected_close_date=None,
        closed_at=None,
        won_reason=None,
        lost_reason=None,
        created_at=now,
        updated_at=now,
    )
    db.add(opp)
    db.flush()

    sh = StageHistory(
        opportunity_id=opp.id,
        from_stage=None,
        to_stage=OpportunityStage.DISCOVERY,
        transitioned_at=now,
        actor="system:opportunity_engine",
        notes="Opportunity created",
    )
    db.add(sh)

    # Update lead lifecycle if not already CONVERTED
    if lead.status != LeadStatus.CONVERTED:
        lead.status = LeadStatus.CONVERTED
        lead.converted_at = now

    db.flush()
    return OpportunityCreated(opportunity=opp, stage_history=sh)


def advance_stage(
    db: Session,
    opportunity: Opportunity,
    to_stage: OpportunityStage,
    actor: str = "system",
    notes: str | None = None,
    as_of: datetime | None = None,
) -> StageHistory:
    """
    Advance opportunity to `to_stage`.

    Raises:
      - InvalidStageTransition if not strictly forward
      - ValueError if opportunity is already closed (won/lost)
      - InvalidStageTransition if to_stage == CLOSED (must use close_won/close_lost)

    Writes immutable StageHistory row.
    """
    if opportunity.status in (OpportunityStatus.WON, OpportunityStatus.LOST):
        raise ValueError(
            f"Cannot advance stage: opportunity {opportunity.business_id} is already {opportunity.status.value}"
        )

    # NEW GUARD: CLOSED must go through close_won() or close_lost()
    if to_stage == OpportunityStage.CLOSED:
        raise InvalidStageTransition(
            "Cannot advance directly to CLOSED. Use close_won() or close_lost() "
            "to set the terminal outcome (won_reason or lost_reason)."
        )

    _validate_forward_transition(opportunity.stage, to_stage)

    now = as_of or datetime.now(timezone.utc)
    from_stage = opportunity.stage

    opportunity.stage = to_stage
    opportunity.updated_at = now

    sh = StageHistory(
        opportunity_id=opportunity.id,
        from_stage=from_stage,
        to_stage=to_stage,
        transitioned_at=now,
        actor=actor,
        notes=notes,
    )
    db.add(sh)
    db.flush()
    return sh


def close_won(
    db: Session,
    opportunity: Opportunity,
    won_reason: str | None = None,
    actor: str = "system",
    as_of: datetime | None = None,
) -> StageHistory:
    """
    Close opportunity as won. Writes StageHistory (from current stage → CLOSED).
    Sets closed_at, won_reason, status=WON.
    """
    if opportunity.status != OpportunityStatus.OPEN:
        raise ValueError(f"Cannot close: opportunity already {opportunity.status.value}")

    now = as_of or datetime.now(timezone.utc)
    from_stage = opportunity.stage

    # If not already at CLOSED, move there
    if from_stage != OpportunityStage.CLOSED:
        _validate_forward_transition(from_stage, OpportunityStage.CLOSED)

    opportunity.stage = OpportunityStage.CLOSED
    opportunity.status = OpportunityStatus.WON
    opportunity.closed_at = now
    opportunity.won_reason = won_reason or "Closed won"
    opportunity.lost_reason = None
    opportunity.updated_at = now

    sh = StageHistory(
        opportunity_id=opportunity.id,
        from_stage=from_stage,
        to_stage=OpportunityStage.CLOSED,
        transitioned_at=now,
        actor=actor,
        notes=f"WON: {won_reason or 'no reason'}",
    )
    db.add(sh)
    db.flush()
    return sh


def close_lost(
    db: Session,
    opportunity: Opportunity,
    lost_reason: LostReason,
    actor: str = "system",
    as_of: datetime | None = None,
) -> StageHistory:
    """
    Close opportunity as lost. Requires lost_reason (from U7 enum).
    Writes StageHistory.
    """
    if opportunity.status != OpportunityStatus.OPEN:
        raise ValueError(f"Cannot close: opportunity already {opportunity.status.value}")

    now = as_of or datetime.now(timezone.utc)
    from_stage = opportunity.stage

    if from_stage != OpportunityStage.CLOSED:
        _validate_forward_transition(from_stage, OpportunityStage.CLOSED)

    opportunity.stage = OpportunityStage.CLOSED
    opportunity.status = OpportunityStatus.LOST
    opportunity.closed_at = now
    opportunity.won_reason = None
    opportunity.lost_reason = lost_reason
    opportunity.updated_at = now

    sh = StageHistory(
        opportunity_id=opportunity.id,
        from_stage=from_stage,
        to_stage=OpportunityStage.CLOSED,
        transitioned_at=now,
        actor=actor,
        notes=f"LOST: {lost_reason.value}",
    )
    db.add(sh)
    db.flush()
    return sh
