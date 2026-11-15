"""
Marketing domain — 5 tables.

Campaign, Lead, LeadCampaign (bridge), Activity, Consent.
Parent-before-child: Campaigns before Leads; Leads before Activities/Consent.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    text,
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
    ActivityType,
    CampaignStatus,
    ConsentChannel,
    ConsentStatus,
    LeadSource,
    LeadStatus,
    ScoreCategory,
)


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="CMP-0001 format",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[LeadSource] = mapped_column(nullable=False, index=True)
    status: Mapped[CampaignStatus] = mapped_column(nullable=False, index=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    budget_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        CheckConstraint("budget_usd >= 0", name="ck_campaign_budget_nonneg"),
        CheckConstraint(
            "end_date IS NULL OR end_date > start_date",
            name="ck_campaign_end_after_start",
        ),
    )

    lead_links: Mapped[list[LeadCampaign]] = relationship(back_populates="campaign")


class Lead(Base, TimestampMixin):
    """Core lead entity. Score fields are denormalized current-state (history in LeadScoreHistory)."""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="LEAD-2026-000001 format",
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    source: Mapped[LeadSource] = mapped_column(nullable=False, index=True)
    status: Mapped[LeadStatus] = mapped_column(
        nullable=False, index=True, default=LeadStatus.NEW
    )

    # --- Denormalized current score (immutable history in LeadScoreHistory) ---
    current_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    current_score_category: Mapped[ScoreCategory | None] = mapped_column(
        nullable=True, index=True
    )
    current_score_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Routing ---
    assigned_rep_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=True, index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Conversion tracking ---
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # --- Operational flags ---
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        doc="False for records injected as anomalies (never counted in baseline KPIs).",
    )
    territory_id: Mapped[int] = mapped_column(
        ForeignKey("territories.id"), nullable=False, index=True
    )
    product_interest: Mapped[str] = mapped_column(
        String(255), nullable=False, default="",
        doc="Comma-separated product codes.",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "current_score IS NULL OR (current_score >= 0 AND current_score <= 100)",
            name="ck_lead_score_range",
        ),
        Index(
            "ix_lead_assigned_active",
            "assigned_rep_id",
            postgresql_where=text(
                "status IN ('QUALIFIED', 'ASSIGNED', 'WORKING')"
            ),
        ),
    )

    campaign_links: Mapped[list[LeadCampaign]] = relationship(back_populates="lead")
    activities: Mapped[list[Activity]] = relationship(back_populates="lead")
    consents: Mapped[list[Consent]] = relationship(back_populates="lead")


class LeadCampaign(Base):
    """Many-to-many bridge — a lead can be attributed to multiple campaigns."""
    __tablename__ = "lead_campaigns"

    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    attributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lead: Mapped[Lead] = relationship(back_populates="campaign_links")
    campaign: Mapped[Campaign] = relationship(back_populates="lead_links")


class Activity(Base, TimestampMixin):
    """Engagement event. IMMUTABLE — never updated after insert."""
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        doc="ACT-<lead-id>-001 format",
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type: Mapped[ActivityType] = mapped_column(nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Free-form JSON string (channel, campaign, utm, etc)."
    )

    __table_args__ = (
        Index("ix_activity_lead_time", "lead_id", "occurred_at"),
    )

    lead: Mapped[Lead] = relationship(back_populates="activities")


class Consent(Base, TimestampMixin):
    """
    A1: per-channel consent. One row per (lead, channel).
    IMMUTABLE history: consent changes create new rows; latest by changed_at wins.
    """
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        doc="CONSENT-<lead-id>-<seq> format",
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[ConsentChannel] = mapped_column(nullable=False, index=True)
    status: Mapped[ConsentStatus] = mapped_column(nullable=False, index=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_consent_lead_channel_time", "lead_id", "channel", "changed_at"),
    )

    lead: Mapped[Lead] = relationship(back_populates="consents")

