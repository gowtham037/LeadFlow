"""
Anomaly injection — the 5 mandatory negative scenarios.

Each anomaly lives on a NEW record (is_baseline=False) so baseline KPIs stay
100% clean. Ground truth labels are written to data/ground_truth/ground_truth.csv
and NEVER used by any engine.

Scenarios:
  1. optout_contacted          — task created for a revoked-consent lead
  2. post_conversion_scoring   — score_history includes post-converted activity
  3. territory_mismatch        — lead assigned to rep outside its territory
  4. duplicate_opportunity     — 2 opportunities for one lead
  5. stage_gap                 — stage history skips a stage (discovery → proposal)
"""
from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.ids import (
    SEQ_EXCEPTION,
    SEQ_LEAD,
    SEQ_OPP,
    activity_id,
    task_id,
)
from backend.app.models.enums import (
    ActivityType,
    ConsentChannel,
    ConsentStatus,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    LeadSource,
    LeadStatus,
    LostReason,
    OpportunityStage,
    OpportunityStatus,
    ProductTier,
    ScoreCategory,
    TaskPriority,
    TaskStatus,
)
from backend.app.models.marketing import Activity, Consent, Lead
from backend.app.models.organization import Company, Contact, Product, SalesRep
from backend.app.models.sales_ops import Opportunity, StageHistory, Task
from backend.app.models.system import ExceptionRecord


GROUND_TRUTH_PATH = Path("data/ground_truth/ground_truth.csv")


def _write_ground_truth(rows: list[dict]) -> None:
    GROUND_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GROUND_TRUTH_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "anomaly_id", "anomaly_type", "entity_type", "entity_id",
                "expected_behavior", "actual_behavior", "severity", "injected_at",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def inject_anomalies(
    db: Session,
    companies: list[Company],
    contacts: list[Contact],
    products: list[Product],
    sales_reps: list[SalesRep],
    seed: int,
) -> list[ExceptionRecord]:
    fake = Faker()
    Faker.seed(seed + 10)

    if len(companies) < 5:
        raise RuntimeError("Need at least 5 companies to inject 5 anomalies")

    records: list[ExceptionRecord] = []
    ground_truth: list[dict] = []
    now = fake.date_time_between(start_date="-30d", end_date="now")

    def make_lead(company: Company, **overrides) -> Lead:
        contact = fake.random_element(
            elements=[c for c in contacts if c.company_id == company.id]
        )
        base = dict(
            business_id=SEQ_LEAD.next(),
            contact_id=contact.id,
            company_id=company.id,
            source=LeadSource.INBOUND_FORM,
            status=LeadStatus.WORKING,
            current_score=85,
            current_score_category=ScoreCategory.HOT,
            current_score_version="v1",
            last_scored_at=now,
            assigned_rep_id=sales_reps[0].id,
            assigned_at=now,
            converted_at=None,
            is_duplicate=False,
            is_baseline=False,
            territory_id=company.territory_id,
            product_interest=products[0].code,
            notes="Anomaly record — is_baseline=False",
        )
        base.update(overrides)
        lead = Lead(**base)
        db.add(lead)
        db.flush()
        return lead

    def make_exception(anomaly_type, entity_type, entity_id, expected, actual, severity):
        rec = ExceptionRecord(
            business_id=SEQ_EXCEPTION.next(),
            entity_type=entity_type,
            entity_id=entity_id,
            issue_type=anomaly_type,
            severity=severity,
            detected_at=now,
            expected_behavior=expected,
            actual_behavior=actual,
            ground_truth_class=anomaly_type.value,
            status=ExceptionStatus.OPEN,
            resolved_at=None,
            resolution_details=None,
            resolved_by=None,
        )
        db.add(rec)
        db.flush()
        return rec

    # --- Anomaly 1: optout_contacted ---
    c1 = companies[0]
    lead1 = make_lead(c1)
    # Revoke all consents
    for ch in [ConsentChannel.EMAIL, ConsentChannel.PHONE]:
        db.add(Consent(
            business_id=f"CONSENT-{lead1.business_id}-{ch.value}",
            lead_id=lead1.id,
            channel=ch,
            status=ConsentStatus.REVOKED,
            changed_at=now,
            reason="opt_out_form",
        ))
    # Create a task anyway — VIOLATION
    task1 = Task(
        business_id=task_id(lead1.business_id, 1),
        lead_id=lead1.id,
        assigned_rep_id=sales_reps[0].id,
        title="Follow up (ANOMALY: consent violated)",
        description="Injected anomaly — task created for opted-out lead",
        priority=TaskPriority.HIGH,
        status=TaskStatus.PENDING,
        due_at=now + timedelta(hours=24),
        sla_deadline_at=now + timedelta(hours=24),
        completed_at=None,
        consent_eligible=False,  # snapshot: NOT eligible but created anyway
        triggering_rule="ANOMALY_optout_contacted",
    )
    db.add(task1)
    db.flush()
    rec1 = make_exception(
        ExceptionType.OPTOUT_CONTACTED, "task", task1.business_id,
        expected="No task created for leads with all consent channels revoked",
        actual=f"Task {task1.business_id} created for opted-out lead {lead1.business_id}",
        severity=ExceptionSeverity.CRITICAL,
    )
    records.append(rec1)
    ground_truth.append({
        "anomaly_id": rec1.business_id, "anomaly_type": "optout_contacted",
        "entity_type": "task", "entity_id": task1.business_id,
        "expected_behavior": rec1.expected_behavior,
        "actual_behavior": rec1.actual_behavior,
        "severity": "critical", "injected_at": now.isoformat(),
    })

    # --- Anomaly 2: post_conversion_scoring ---
    c2 = companies[1]
    lead2 = make_lead(c2, status=LeadStatus.CONVERTED)
    conv_time = now - timedelta(days=10)
    lead2.converted_at = conv_time
    db.flush()
    # An activity that occurred AFTER conversion should NEVER influence a pre-conversion score
    act2 = Activity(
        business_id=activity_id(lead2.business_id, 999),
        lead_id=lead2.id,
        activity_type=ActivityType.DEMO_REQUEST,
        occurred_at=conv_time + timedelta(days=5),  # POST conversion
        metadata_json=json.dumps({"anomaly": "post_conversion_scoring"}),
    )
    db.add(act2)
    db.flush()
    rec2 = make_exception(
        ExceptionType.POST_CONVERSION_SCORING, "activity", act2.business_id,
        expected="Scoring engine only uses activities occurring before conversion",
        actual=f"Activity {act2.business_id} occurred 5 days AFTER conversion — violates cutoff",
        severity=ExceptionSeverity.HIGH,
    )
    records.append(rec2)
    ground_truth.append({
        "anomaly_id": rec2.business_id, "anomaly_type": "post_conversion_scoring",
        "entity_type": "activity", "entity_id": act2.business_id,
        "expected_behavior": rec2.expected_behavior,
        "actual_behavior": rec2.actual_behavior,
        "severity": "high", "injected_at": now.isoformat(),
    })

    # --- Anomaly 3: territory_mismatch ---
    c3 = companies[2]
    # Find a rep in a DIFFERENT territory
    other_territory_rep = next(
        r for r in sales_reps if r.territory_id != c3.territory_id
    )
    lead3 = make_lead(
        c3,
        assigned_rep_id=other_territory_rep.id,
        territory_id=c3.territory_id,
    )
    rec3 = make_exception(
        ExceptionType.TERRITORY_MISMATCH, "lead", lead3.business_id,
        expected=f"Lead assigned to rep in territory {c3.territory_id}",
        actual=f"Lead assigned to rep in territory {other_territory_rep.territory_id}",
        severity=ExceptionSeverity.HIGH,
    )
    records.append(rec3)
    ground_truth.append({
        "anomaly_id": rec3.business_id, "anomaly_type": "territory_mismatch",
        "entity_type": "lead", "entity_id": lead3.business_id,
        "expected_behavior": rec3.expected_behavior,
        "actual_behavior": rec3.actual_behavior,
        "severity": "high", "injected_at": now.isoformat(),
    })

    # --- Anomaly 4: duplicate_opportunity ---
    c4 = companies[3]
    lead4 = make_lead(c4, status=LeadStatus.CONVERTED)
    conv_time4 = now - timedelta(days=20)
    lead4.converted_at = conv_time4
    db.flush()
    opp4a = Opportunity(
        business_id=SEQ_OPP.next(),
        lead_id=lead4.id,
        rep_id=sales_reps[0].id,
        name="Opp A (legitimate)",
        amount_usd=10000,
        stage=OpportunityStage.DISCOVERY,
        status=OpportunityStatus.OPEN,
        expected_close_date=now + timedelta(days=90),
        closed_at=None,
        won_reason=None,
        lost_reason=None,
    )
    db.add(opp4a)
    db.flush()
    # duplicate — should be caught by uq_opportunity_lead unique constraint,
    # so we bypass by using a fresh business_id with a placeholder lead_id... 
    # Actually: we can't insert a 2nd opp with same lead_id due to unique constraint.
    # So we demonstrate the DUPLICATE by adding to a *new lead* that shares the
    # same contact+company as lead4. This simulates the "same prospect, duplicate lead" case.
    dup_lead4 = make_lead(
        c4,
        status=LeadStatus.CONVERTED,
        contact_id=lead4.contact_id,
    )
    dup_lead4.converted_at = conv_time4 + timedelta(hours=1)
    dup_lead4.is_duplicate = True
    db.flush()
    opp4b = Opportunity(
        business_id=SEQ_OPP.next(),
        lead_id=dup_lead4.id,
        rep_id=sales_reps[0].id,
        name="Opp B (DUPLICATE — same contact+company)",
        amount_usd=10000,
        stage=OpportunityStage.DISCOVERY,
        status=OpportunityStatus.OPEN,
        expected_close_date=now + timedelta(days=90),
        closed_at=None,
        won_reason=None,
        lost_reason=None,
    )
    db.add(opp4b)
    db.flush()
    rec4 = make_exception(
        ExceptionType.DUPLICATE_OPPORTUNITY, "opportunity", opp4b.business_id,
        expected="One opportunity per unique prospect (contact+company)",
        actual=f"Opportunity {opp4b.business_id} duplicates {opp4a.business_id} on same contact+company",
        severity=ExceptionSeverity.HIGH,
    )
    records.append(rec4)
    ground_truth.append({
        "anomaly_id": rec4.business_id, "anomaly_type": "duplicate_opportunity",
        "entity_type": "opportunity", "entity_id": opp4b.business_id,
        "expected_behavior": rec4.expected_behavior,
        "actual_behavior": rec4.actual_behavior,
        "severity": "high", "injected_at": now.isoformat(),
    })

    # --- Anomaly 5: stage_gap ---
    c5 = companies[4]
    lead5 = make_lead(c5, status=LeadStatus.CONVERTED)
    conv_time5 = now - timedelta(days=15)
    lead5.converted_at = conv_time5
    db.flush()
    opp5 = Opportunity(
        business_id=SEQ_OPP.next(),
        lead_id=lead5.id,
        rep_id=sales_reps[0].id,
        name="Opp with stage gap",
        amount_usd=50000,
        stage=OpportunityStage.PROPOSAL,
        status=OpportunityStatus.OPEN,
        expected_close_date=now + timedelta(days=60),
        closed_at=None,
        won_reason=None,
        lost_reason=None,
    )
    db.add(opp5)
    db.flush()
    # Stage history skipping qualification
    db.add(StageHistory(
        opportunity_id=opp5.id,
        from_stage=None,
        to_stage=OpportunityStage.DISCOVERY,
        transitioned_at=conv_time5,
        actor="system:anomaly",
        notes=None,
    ))
    db.add(StageHistory(
        opportunity_id=opp5.id,
        from_stage=OpportunityStage.DISCOVERY,
        to_stage=OpportunityStage.PROPOSAL,  # GAP — skipped qualification
        transitioned_at=conv_time5 + timedelta(days=5),
        actor="system:anomaly",
        notes="ANOMALY: skipped qualification",
    ))
    db.flush()
    rec5 = make_exception(
        ExceptionType.STAGE_GAP, "opportunity", opp5.business_id,
        expected="Stage history follows DISCOVERY → QUALIFICATION → PROPOSAL",
        actual="Skipped QUALIFICATION: DISCOVERY → PROPOSAL directly",
        severity=ExceptionSeverity.MEDIUM,
    )
    records.append(rec5)
    ground_truth.append({
        "anomaly_id": rec5.business_id, "anomaly_type": "stage_gap",
        "entity_type": "opportunity", "entity_id": opp5.business_id,
        "expected_behavior": rec5.expected_behavior,
        "actual_behavior": rec5.actual_behavior,
        "severity": "medium", "injected_at": now.isoformat(),
    })

    db.commit()
    _write_ground_truth(ground_truth)
    return records

