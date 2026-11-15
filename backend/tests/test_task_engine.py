"""
Unit tests for the task engine.

Covers:
  - HOT/WARM/NURTURE get tasks with correct SLA + priority
  - COLD gets no task
  - Consent A1 hard gate: no task if all channels revoked
  - One granted channel is enough
  - No task if no assigned rep
  - No task for pre-QUALIFIED statuses
  - SLA deadline = due date
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.engines.task_management.engine import create_followup_task
from backend.app.models.enums import (
    ConsentChannel,
    ConsentStatus,
    LeadSource,
    LeadStatus,
    ProductTier,
    ScoreCategory,
    TaskPriority,
    TerritoryRegion,
)
from backend.app.models.marketing import Consent, Lead
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
    SL = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SL()
    try:
        yield s
    finally:
        s.close()


_COUNTER = {"n": 0}


def _next() -> int:
    _COUNTER["n"] += 1
    return _COUNTER["n"]


def _seed(db: Session):
    n = _next()
    t = Territory(code=f"TER-{n:04d}", name="NA",
                  region=TerritoryRegion.NORTH_AMERICA, postal_prefixes="0", is_active=True)
    p = Product(code=f"PRD-{n:04d}", name="Basic",
                tier=ProductTier.BASIC, list_price=99, is_active=True)
    db.add_all([t, p]); db.flush()

    company = Company(
        business_id=f"CO-{n:06d}", name="TestCo", industry="Software as a Service",
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


def _lead(db: Session, master, category=ScoreCategory.HOT,
          status=LeadStatus.ASSIGNED, with_rep=True):
    n = _next()
    lead = Lead(
        business_id=f"LEAD-2026-{n:06d}",
        contact_id=master["contact"].id,
        company_id=master["company"].id,
        source=LeadSource.INBOUND_FORM,
        status=status,
        current_score=90 if category == ScoreCategory.HOT else 70 if category == ScoreCategory.WARM else 50 if category == ScoreCategory.NURTURE else 20,
        current_score_category=category,
        current_score_version="v1",
        assigned_rep_id=master["rep"].id if with_rep else None,
        territory_id=master["territory"].id,
        product_interest=master["product"].code,
        is_baseline=True,
        is_duplicate=False,
    )
    db.add(lead); db.flush()
    db.commit()
    return lead


def _consent(db: Session, lead, channel=ConsentChannel.EMAIL,
             status=ConsentStatus.GRANTED):
    c = Consent(
        business_id=f"CONSENT-{lead.business_id}-{channel.value}",
        lead_id=lead.id, channel=channel, status=status,
        changed_at=datetime.now(timezone.utc), reason=None,
    )
    db.add(c); db.commit()
    return c


# --- Tests ---

def test_hot_lead_gets_urgent_1h_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)

    assert task is not None
    assert task.priority == TaskPriority.URGENT
    assert task.triggering_rule == "score_hot_immediate"
    delta = (task.sla_deadline_at - task.created_at).total_seconds()
    assert abs(delta - 3600) < 60


def test_warm_lead_gets_high_24h_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.WARM)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)

    assert task is not None
    assert task.priority == TaskPriority.HIGH
    delta = (task.sla_deadline_at - task.created_at).total_seconds()
    assert abs(delta - 86400) < 60


def test_nurture_lead_gets_medium_72h_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.NURTURE)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)

    assert task is not None
    assert task.priority == TaskPriority.MEDIUM
    delta = (task.sla_deadline_at - task.created_at).total_seconds()
    assert abs(delta - 259200) < 60


def test_cold_lead_gets_no_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.COLD)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)
    assert task is None


def test_consent_hard_gate_all_revoked(db):
    """A1: no task if every channel is revoked."""
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT)
    for ch in (ConsentChannel.EMAIL, ConsentChannel.PHONE,
               ConsentChannel.SMS, ConsentChannel.MARKETING):
        _consent(db, lead, ch, ConsentStatus.REVOKED)

    task = create_followup_task(db, lead)
    assert task is None


def test_consent_one_granted_channel_allows_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.REVOKED)
    _consent(db, lead, ConsentChannel.PHONE, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)
    assert task is not None


def test_no_consent_rows_means_no_task(db):
    """No consent rows at all → treated as no granted channel."""
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT)

    task = create_followup_task(db, lead)
    assert task is None


def test_no_assigned_rep_means_no_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT, with_rep=False)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)
    assert task is None


def test_pre_qualified_status_means_no_task(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT, status=LeadStatus.NEW)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)
    assert task is None


def test_task_business_id_format(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.HOT)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)

    assert task is not None
    assert task.business_id.startswith(f"TASK-{lead.business_id}-")
    assert task.business_id.endswith("001")


def test_sla_deadline_equals_due_at(db):
    m = _seed(db)
    lead = _lead(db, m, category=ScoreCategory.WARM)
    _consent(db, lead, ConsentChannel.EMAIL, ConsentStatus.GRANTED)

    task = create_followup_task(db, lead)

    assert task is not None
    assert task.sla_deadline_at == task.due_at

