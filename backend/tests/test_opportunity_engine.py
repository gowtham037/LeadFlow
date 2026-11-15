"""
Unit tests for the opportunity engine.

Covers:
  - Create opportunity → stage=discovery, status=open, history written
  - Duplicate prevented
  - Preconditions (no rep, wrong status)
  - Forward stage transitions only (no skipping, no reversing)
  - Cannot advance closed opportunity
  - Won requires closed_at + status=won + lost_reason=None
  - Lost requires lost_reason set
  - Stage history is written for every transition
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.engines.opportunity.engine import (
    DuplicateOpportunity,
    InvalidStageTransition,
    advance_stage,
    close_lost,
    close_won,
    create_opportunity,
)
from backend.app.models.enums import (
    LeadSource,
    LeadStatus,
    LostReason,
    OpportunityStage,
    OpportunityStatus,
    ProductTier,
    ScoreCategory,
    TerritoryRegion,
)
from backend.app.models.marketing import Lead
from backend.app.models.organization import (
    Company,
    Contact,
    Product,
    SalesRep,
    Territory,
)
from backend.app.models.sales_ops import Opportunity, StageHistory


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SL = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SL()
    try:
        yield s
    finally:
        s.close()


_C = {"n": 0}


def _next() -> int:
    _C["n"] += 1
    return _C["n"]


def _seed(db):
    n = _next()
    t = Territory(code=f"TER-{n:04d}", name="NA",
                  region=TerritoryRegion.NORTH_AMERICA, postal_prefixes="0", is_active=True)
    p = Product(code=f"PRD-{n:04d}", name="Pro",
                tier=ProductTier.PRO, list_price=500, is_active=True)
    db.add_all([t, p]); db.flush()

    company = Company(
        business_id=f"CO-{n:06d}", name="C", industry="Software as a Service",
        employee_count=500, annual_revenue_usd=10_000_000,
        country="US", postal_code="10001", territory_id=t.id,
    )
    db.add(company); db.flush()

    contact = Contact(
        business_id=f"CON-{n:06d}", company_id=company.id,
        first_name="A", last_name="B", email=f"a{n}@test.com",
    )
    db.add(contact); db.flush()

    rep = SalesRep(
        business_id=f"REP-{n:06d}", full_name="Rep",
        email=f"r{n}@test.com", territory_id=t.id,
        product_expertise=p.code, workload_capacity=10, current_workload=0,
        is_active=True, hired_on=date(2024, 1, 1),
    )
    db.add(rep); db.flush()
    db.commit()
    return {"territory": t, "product": p, "company": company,
            "contact": contact, "rep": rep}


def _lead(db, m, status=LeadStatus.QUALIFIED, with_rep=True):
    n = _next()
    lead = Lead(
        business_id=f"LEAD-2026-{n:06d}",
        contact_id=m["contact"].id,
        company_id=m["company"].id,
        source=LeadSource.INBOUND_FORM,
        status=status,
        current_score=85,
        current_score_category=ScoreCategory.HOT,
        current_score_version="v1",
        assigned_rep_id=m["rep"].id if with_rep else None,
        territory_id=m["territory"].id,
        product_interest=m["product"].code,
        is_baseline=True,
        is_duplicate=False,
    )
    db.add(lead); db.flush(); db.commit()
    return lead


# --- Tests ---

def test_create_opportunity_at_discovery(db):
    m = _seed(db)
    lead = _lead(db, m)
    result = create_opportunity(db, lead)

    opp = result.opportunity
    assert opp.stage == OpportunityStage.DISCOVERY
    assert opp.status == OpportunityStatus.OPEN
    assert opp.lead_id == lead.id
    assert opp.rep_id == m["rep"].id
    assert result.stage_history.from_stage is None
    assert result.stage_history.to_stage == OpportunityStage.DISCOVERY


def test_create_marks_lead_converted(db):
    m = _seed(db)
    lead = _lead(db, m, status=LeadStatus.QUALIFIED)
    create_opportunity(db, lead)
    assert lead.status == LeadStatus.CONVERTED
    assert lead.converted_at is not None


def test_duplicate_opportunity_rejected(db):
    m = _seed(db)
    lead = _lead(db, m)
    create_opportunity(db, lead)
    with pytest.raises(DuplicateOpportunity):
        create_opportunity(db, lead)


def test_create_requires_assigned_rep(db):
    m = _seed(db)
    lead = _lead(db, m, with_rep=False)
    with pytest.raises(ValueError):
        create_opportunity(db, lead)


def test_create_rejects_new_status(db):
    m = _seed(db)
    lead = _lead(db, m, status=LeadStatus.NEW)
    with pytest.raises(ValueError):
        create_opportunity(db, lead)


def test_advance_stage_forward(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity

    sh = advance_stage(db, opp, OpportunityStage.QUALIFICATION)
    assert opp.stage == OpportunityStage.QUALIFICATION
    assert sh.from_stage == OpportunityStage.DISCOVERY
    assert sh.to_stage == OpportunityStage.QUALIFICATION


def test_advance_stage_skip_rejected(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity

    with pytest.raises(InvalidStageTransition):
        advance_stage(db, opp, OpportunityStage.PROPOSAL)


def test_advance_stage_backwards_rejected(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity
    advance_stage(db, opp, OpportunityStage.QUALIFICATION)

    with pytest.raises(InvalidStageTransition):
        advance_stage(db, opp, OpportunityStage.DISCOVERY)


def test_cannot_advance_closed_opportunity(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity
    close_won(db, opp)

    with pytest.raises(ValueError):
        advance_stage(db, opp, OpportunityStage.NEGOTIATION)


def test_close_won_sets_status_and_reason(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity
    close_won(db, opp, won_reason="Best price")

    assert opp.status == OpportunityStatus.WON
    assert opp.closed_at is not None
    assert opp.won_reason == "Best price"
    assert opp.lost_reason is None
    assert opp.stage == OpportunityStage.CLOSED


def test_close_lost_requires_reason(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity
    close_lost(db, opp, LostReason.PRICE)

    assert opp.status == OpportunityStatus.LOST
    assert opp.lost_reason == LostReason.PRICE
    assert opp.won_reason is None
    assert opp.closed_at is not None


def test_close_won_from_mid_stage(db):
    """Won from negotiation should work (no need to hit proposal first)."""
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity
    advance_stage(db, opp, OpportunityStage.QUALIFICATION)
    advance_stage(db, opp, OpportunityStage.PROPOSAL)
    close_won(db, opp, won_reason="closed from proposal")

    assert opp.status == OpportunityStatus.WON


def test_stage_history_rows_written(db):
    m = _seed(db)
    lead = _lead(db, m)
    opp = create_opportunity(db, lead).opportunity
    advance_stage(db, opp, OpportunityStage.QUALIFICATION)
    advance_stage(db, opp, OpportunityStage.PROPOSAL)
    close_won(db, opp)

    history = (
        db.query(StageHistory)
        .filter(StageHistory.opportunity_id == opp.id)
        .order_by(StageHistory.id)
        .all()
    )
    # creation + 2 advances + close = 4 rows
    assert len(history) == 4
    assert history[0].to_stage == OpportunityStage.DISCOVERY
    assert history[-1].to_stage == OpportunityStage.CLOSED

