"""
Organization domain — 5 master tables.

Company, Contact, Territory, Product, SalesRep.
Generated before transactional tables (parent-before-child per InsureFlow).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.models.base import TimestampMixin
from backend.app.models.enums import ProductTier, TerritoryRegion


class Territory(Base, TimestampMixin):
    __tablename__ = "territories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[TerritoryRegion] = mapped_column(nullable=False)
    postal_prefixes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
        doc="Comma-separated postal prefixes that route to this territory.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("length(code) >= 2", name="ck_territory_code_len"),
    )

    sales_reps: Mapped[list[SalesRep]] = relationship(back_populates="territory")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[ProductTier] = mapped_column(nullable=False)
    list_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("list_price >= 0", name="ck_product_price_nonneg"),
    )


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="CO-000001 format",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_revenue_usd: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, doc="ISO 3166-1 alpha-2")
    postal_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    territory_id: Mapped[int] = mapped_column(
        ForeignKey("territories.id"), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint("employee_count >= 0", name="ck_company_emp_nonneg"),
        CheckConstraint("annual_revenue_usd >= 0", name="ck_company_rev_nonneg"),
        CheckConstraint("length(country) = 2", name="ck_company_country_iso2"),
    )

    territory: Mapped[Territory] = relationship()
    contacts: Mapped[list[Contact]] = relationship(back_populates="company")


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="CON-000001 format",
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint("email", name="uq_contact_email"),
        CheckConstraint("email LIKE '%@%'", name="ck_contact_email_at"),
    )

    company: Mapped[Company] = relationship(back_populates="contacts")


class SalesRep(Base, TimestampMixin):
    __tablename__ = "sales_reps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        doc="REP-0001 format",
    )
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    territory_id: Mapped[int] = mapped_column(
        ForeignKey("territories.id"), nullable=False, index=True
    )
    product_expertise: Mapped[str] = mapped_column(
        String(255), nullable=False, default="",
        doc="Comma-separated product codes this rep can sell.",
    )
    workload_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50,
        doc="A4: max concurrent open leads + open opps.",
    )
    current_workload: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        doc="A4: incremented/decremented by routing + opp engines.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hired_on: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint("workload_capacity > 0", name="ck_rep_capacity_pos"),
        CheckConstraint("current_workload >= 0", name="ck_rep_workload_nonneg"),
    )

    territory: Mapped[Territory] = relationship(back_populates="sales_reps")

