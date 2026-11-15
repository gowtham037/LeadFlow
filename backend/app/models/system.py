"""
System domain — 4 tables.

User, Role, ExceptionRecord, AuditLog.
ExceptionRecord is first-class per spec — anomalies are surfaced, never silently fixed.
AuditLog is IMMUTABLE — every important state change appends one row.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.models.base import TimestampMixin
from backend.app.models.enums import (
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    UserRole,
)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[UserRole] = mapped_column(unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="USR-0001 format",
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("email LIKE '%@%'", name="ck_user_email_at"),
    )

    role: Mapped[Role] = relationship()


class ExceptionRecord(Base, TimestampMixin):
    """
    Explicit exception record — every anomaly is one of these.
    Spec: Exception ID, Entity ID, Issue type, Severity, Detection ts,
          Expected behavior, Actual behavior, Ground-truth class, Resolution status/details.
    """
    __tablename__ = "exception_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="EXC-2026-000001 format",
    )
    entity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        doc="lead | opportunity | task | stage_history | etc.",
    )
    entity_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        doc="Business ID of the offending entity.",
    )
    issue_type: Mapped[ExceptionType] = mapped_column(nullable=False, index=True)
    severity: Mapped[ExceptionSeverity] = mapped_column(nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    actual_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    ground_truth_class: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        doc="Injected anomaly label (from ground_truth.csv), never used as engine input.",
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        nullable=False, index=True, default=ExceptionStatus.OPEN
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_exc_type_status", "issue_type", "status"),
    )


class AuditLog(Base):
    """IMMUTABLE append-only state-change log."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        doc="create_lead | assign_lead | convert_lead | change_stage | etc.",
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    __table_args__ = (
        Index("ix_audit_entity_time", "entity_type", "entity_id", "occurred_at"),
    )

