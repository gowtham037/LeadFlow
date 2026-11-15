"""
Unit tests for the routing engine.

Uses an in-memory SQLite DB with real models (no external Postgres).
Tests territory match, product match, workload, load-balancing, determinism.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.engines.routing.engine import route_lead
from backend.app.models.enums import (
    LeadSource,
    LeadStatus,
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


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed_master(db: Session):
    territories = [
        Territory(code="TER-0001", name="NA", region=TerritoryRegion.NORTH_AMERICA,
                  postal_prefixes="0,1,2", is_active=True),
        Territory(code="TER-0002", name="EMEA", region=TerritoryRegion.EMEA,
                  postal_prefixes="", is_active=True),
    ]
    db.add_all(territories)
    db.flush()

    products = [
        Product(code="PRD-0001", name="Basic", tier=ProductTier.BASIC,
                list_price=99, is_active=True),
        Product(code="PRD-0002", name="Pro", tier=ProductTier.PRO,
                list_price=599, is_active=True),
    ]
    db.add_all(products)
    db.flush()

    company = Company(
        business_id="CO-000001", name="Test Co", industry="Software as a Service",
        employee_count=500, annual_revenue_usd=10_000_000,
        country="US", postal_code="10001", territory_id=territories[0].id,
    )
    db.add(company)
    db.flush()

    contact = Contact(
        business_id="CON-000001", company_id=company.id,
        first_name="John", last_name="Doe", email="john@testco.com",
        phone="+15550001111", title="CTO",
    )
    db.add(contact)
    db.flush()

    db.commit()
    return {
        "territories": territories,
        "products": products,
        "company": company,
        "contact": contact,
    }


_REP_COUNTER = {"n": 0}


def _make_rep(db, territory_id, product_codes, workload=0, capacity=10, active=True):
    _REP_COUNTER["n"] += 1
    n = _REP_COUNTER["n"]
    rep = SalesRep(
        business_id=f"REP-{n:04d}",
        full_name=f"Rep Test {n}",
        email=f"rep{n:04d}@test.com",
        territory_id=territory_id,
        product_expertise=product_codes,
        workload_capacity=capacity,
        current_workload=workload,
        is_active=active,
        hired_on=__import__("datetime").date(2024, 1, 1),
    )
    db.add(rep)
    db.commit()
    return rep


def _make_lead(db, master, product_interest="PRD-0001", territory_id=None):
    lead = Lead(
        business_id="LEAD-2026-000001",
        contact_id=master["contact"].id,
        company_id=master["company"].id,
        source=LeadSource.INBOUND_FORM,
        status=LeadStatus.QUALIFIED,
        current_score=85,
        current_score_category=ScoreCategory.HOT,
        current_score_version="v1",
        territory_id=territory_id or master["territories"][0].id,
        product_interest=product_interest,
        is_baseline=True,
        is_duplicate=False,
    )
    db.add(lead)
    db.commit()
    return lead


# --- Tests ---

def test_routes_to_territory_rep_with_capacity(db):
    master = _seed_master(db)
    rep = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=2, capacity=10)
    lead = _make_lead(db, master)

    decision = route_lead(lead, db)

    assert decision.assigned is True
    assert decision.assigned_rep_id == rep.id
    assert decision.reason.value in ("territory_product_match", "territory_only")


def test_prefers_product_match_rep(db):
    master = _seed_master(db)
    # Rep A: same territory, no product match
    rep_a = _make_rep(db, master["territories"][0].id, "PRD-0002", workload=0, capacity=10)
    # Rep B: same territory, product match
    rep_b = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=0, capacity=10)
    lead = _make_lead(db, master, product_interest="PRD-0001")

    decision = route_lead(lead, db)

    assert decision.assigned_rep_id == rep_b.id
    assert decision.reason.value == "territory_product_match"


def test_prefers_lowest_utilization(db):
    master = _seed_master(db)
    # Both match product; one has lower utilization
    rep_high = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=8, capacity=10)
    rep_low = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=2, capacity=10)
    lead = _make_lead(db, master, product_interest="PRD-0001")

    decision = route_lead(lead, db)

    assert decision.assigned_rep_id == rep_low.id


def test_skips_reps_at_capacity(db):
    master = _seed_master(db)
    full_rep = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=10, capacity=10)
    available = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=2, capacity=10)
    lead = _make_lead(db, master, product_interest="PRD-0001")

    decision = route_lead(lead, db)

    assert decision.assigned_rep_id == available.id


def test_skips_wrong_territory(db):
    master = _seed_master(db)
    # Only rep is in EMEA, lead is in NA
    _make_rep(db, master["territories"][1].id, "PRD-0001", workload=0, capacity=10)
    lead = _make_lead(db, master, territory_id=master["territories"][0].id)

    decision = route_lead(lead, db)

    assert decision.assigned is False
    assert decision.reason is None
    assert "no eligible reps" in decision.decision_notes.lower()


def test_skips_inactive_reps(db):
    master = _seed_master(db)
    _make_rep(db, master["territories"][0].id, "PRD-0001",
              workload=0, capacity=10, active=False)
    lead = _make_lead(db, master)

    decision = route_lead(lead, db)

    assert decision.assigned is False


def test_returns_unroutable_when_all_at_capacity(db):
    master = _seed_master(db)
    _make_rep(db, master["territories"][0].id, "PRD-0001", workload=10, capacity=10)
    lead = _make_lead(db, master)

    decision = route_lead(lead, db)

    assert decision.assigned is False
    assert decision.assigned_rep_id is None


def test_deterministic_tie_break(db):
    master = _seed_master(db)
    # Same utilization, same match → lowest rep.id wins
    rep_1 = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=0, capacity=10)
    rep_2 = _make_rep(db, master["territories"][0].id, "PRD-0001", workload=0, capacity=10)
    lead = _make_lead(db, master)

    decision1 = route_lead(lead, db)
    decision2 = route_lead(lead, db)

    assert decision1.assigned_rep_id == decision2.assigned_rep_id
    assert decision1.assigned_rep_id == min(rep_1.id, rep_2.id)


def test_eligible_reps_list_populated(db):
    master = _seed_master(db)
    _make_rep(db, master["territories"][0].id, "PRD-0001", workload=0, capacity=10)
    _make_rep(db, master["territories"][0].id, "PRD-0002", workload=2, capacity=10)
    lead = _make_lead(db, master, product_interest="PRD-0001")

    decision = route_lead(lead, db)

    assert len(decision.eligible_reps) == 2
    assert all(c.territory_match for c in decision.eligible_reps)


def test_product_only_rep_not_selected_for_wrong_territory(db):
    master = _seed_master(db)
    _make_rep(db, master["territories"][1].id, "PRD-0001", workload=0, capacity=10)
    lead = _make_lead(db, master, territory_id=master["territories"][0].id)

    decision = route_lead(lead, db)

    assert decision.assigned is False

