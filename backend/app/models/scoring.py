"""
Scoring domain — 2 tables.

ScoreRule (versioned, configurable) + LeadScoreHistory (immutable).
Ground truth never enters these tables — the scoring engine reads only
features bounded by `input_cutoff_at`.
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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.models.base import TimestampMixin
from backend.app.models.enums import ScoreCategory


class ScoreRule(Base, TimestampMixin):
    """
    Versioned scoring rule. A new version = a new row. Old rows are immutable.
    Weights sum to 100 (validated by check constraint).
    """
    __tablename__ = "score_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False, index=True, doc="v1, v2, ..."
    )
    fit_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    intent_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    engagement_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    recency_weight: Mapped[int] = mapped_column(Integer, nullable=False)

    hot_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    warm_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    nurture_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=40)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "fit_weight + intent_weight + engagement_weight + recency_weight = 100",
            name="ck_score_rule_weights_sum_100",
        ),
        CheckConstraint(
            "hot_threshold > warm_threshold AND warm_threshold > nurture_threshold "
            "AND nurture_threshold >= 0 AND hot_threshold <= 100",
            name="ck_score_rule_thresholds_monotonic",
        ),
    )


class LeadScoreHistory(Base):
    """
    IMMUTABLE score snapshot. Every score calculation appends one row.
    Contributions are stored as JSON text so they can be rendered verbatim
    in the UI without recomputation.
    """
    __tablename__ = "lead_score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False)

    # --- Inputs captured at scoring time ---
    input_cutoff_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="Scores use only events where occurred_at <= input_cutoff_at.",
    )
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # --- Component scores (0-100 each, weighted sum = total_score) ---
    fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    intent_score: Mapped[int] = mapped_column(Integer, nullable=False)
    engagement_score: Mapped[int] = mapped_column(Integer, nullable=False)
    recency_score: Mapped[int] = mapped_column(Integer, nullable=False)

    total_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score_category: Mapped[ScoreCategory] = mapped_column(nullable=False, index=True)

    # --- Explainability: JSON-encoded feature contributions ---
    contributions_json: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="[{feature, value, raw_points, weighted_points, explanation}, ...]",
    )

    __table_args__ = (
        CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_lsh_total_range"),
        CheckConstraint("fit_score >= 0 AND fit_score <= 100", name="ck_lsh_fit_range"),
        CheckConstraint("intent_score >= 0 AND intent_score <= 100", name="ck_lsh_intent_range"),
        CheckConstraint("engagement_score >= 0 AND engagement_score <= 100", name="ck_lsh_engage_range"),
        CheckConstraint("recency_score >= 0 AND recency_score <= 100", name="ck_lsh_recency_range"),
        Index("ix_lsh_lead_time", "lead_id", "scored_at"),
    )

