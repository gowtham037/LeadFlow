"""
Sales operations domain — 5 tables.

Task, LeadAssignmentHistory, Opportunity, StageHistory, DuplicateGroup.
All historical tables (assignment history, stage history) are immutable.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.models.base import TimestampMixin
from backend.app.models.enums import (
    AssignmentReason,
    LostReason,
    OpportunityStage,
    OpportunityStatus,
    TaskPriority,
    TaskStatus,
)


class Task(Base, TimestampMixin):
    """Follow-up task. Enforces A6: no task if consent revoked for the channel."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        doc="TASK-<lead-id>-001 format",
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_rep_id: Mapped[int] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    priority: Mapped[TaskPriority] = mapped_column(nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        nullable=False, index=True, default=TaskStatus.PENDING
    )

    # --- SLA tracking (U2) ---
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sla_deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Consent eligibility snapshot at creation time (audit) ---
    consent_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    triggering_rule: Mapped[str] = mapped_column(
        String(64), nullable=False,
        doc="e.g. score_hot_immediate, score_warm_24h, nurture_scheduled",
    )

    __table_args__ = (
        CheckConstraint("sla_deadline_at >= due_at", name="ck_task_sla_after_due"),
        Index("ix_task_rep_status_due", "assigned_rep_id", "status", "due_at"),
    )


class LeadAssignmentHistory(Base):
    """IMMUTABLE — one row per assignment event (initial + reassignment)."""
    __tablename__ = "lead_assignment_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_rep_id: Mapped[int] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=False, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    reason: Mapped[AssignmentReason] = mapped_column(nullable=False)

    # --- Explainability payload ---
    territory_considered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_required: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eligible_reps_json: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="[{rep_id, workload, capacity, matched_on}, ...]",
    )
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    workload_at_assignment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_lah_lead_time", "lead_id", "assigned_at"),
    )


class Opportunity(Base, TimestampMixin):
    """Converted opportunity. One per lead (uniqueness enforced)."""
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="OPP-2026-000001 format",
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id"), nullable=False, index=True,
        doc="One-to-one — see UniqueConstraint below.",
    )
    rep_id: Mapped[int] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    stage: Mapped[OpportunityStage] = mapped_column(
        nullable=False, index=True, default=OpportunityStage.DISCOVERY
    )
    status: Mapped[OpportunityStatus] = mapped_column(
        nullable=False, index=True, default=OpportunityStatus.OPEN
    )

    expected_close_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # --- Won/lost capture (U7: lost_reason enum) ---
    won_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lost_reason: Mapped[LostReason | None] = mapped_column(nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("lead_id", name="uq_opportunity_lead"),
        CheckConstraint("amount_usd >= 0", name="ck_opp_amount_nonneg"),
        CheckConstraint(
            "(status = 'WON' AND lost_reason IS NULL AND closed_at IS NOT NULL) "
            "OR (status = 'LOST' AND lost_reason IS NOT NULL AND closed_at IS NOT NULL) "
            "OR (status = 'OPEN' AND closed_at IS NULL)",
            name="ck_opp_status_outcome_consistency",
        ),
        Index("ix_opp_rep_status", "rep_id", "status"),
    )


class StageHistory(Base):
    """IMMUTABLE — one row per stage transition."""
    __tablename__ = "stage_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage: Mapped[OpportunityStage | None] = mapped_column(
        nullable=True, doc="NULL for creation event."
    )
    to_stage: Mapped[OpportunityStage] = mapped_column(nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "from_stage IS NULL OR from_stage <> to_stage",
            name="ck_stage_history_no_self_transition",
        ),
        Index("ix_stage_opp_time", "opportunity_id", "transitioned_at"),
    )


class DuplicateGroup(Base, TimestampMixin):
    """Group of leads judged duplicates. Human review required for ambiguous cases."""
    __tablename__ = "duplicate_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="DUP-000001 format",
    )
    primary_lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id"), nullable=False, index=True,
        doc="Canonical lead; duplicates point to this via lead_duplicates.",
    )
    match_signals: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="JSON: [{signal: 'email', value: '...', confidence: 0.95}, ...]",
    )
    confidence: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False,
        doc="0.000-1.000; exact=1.0, fuzzy=(0..1).",
    )
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_dup_confidence_range"),
    )

