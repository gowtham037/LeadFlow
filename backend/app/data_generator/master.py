"""
Master data generator — territories, products, roles, users, sales reps, campaigns.

Deterministic via Faker seed 20261022. Parent-before-child:
  territories → products → roles → users → sales_reps → campaigns
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.utils import weighted_choice
from backend.app.data_generator.ids import (
    SEQ_CAMPAIGN,
    SEQ_PRODUCT_CODE,
    SEQ_REP,
    SEQ_TERRITORY_CODE,
    SEQ_USER,
)
from backend.app.models.enums import (
    CampaignStatus,
    LeadSource,
    ProductTier,
    TerritoryRegion,
    UserRole,
)
from backend.app.models.organization import Product, SalesRep, Territory
from backend.app.models.marketing import Campaign
from backend.app.models.system import Role, User


def _ensure_roles(db: Session) -> dict[UserRole, Role]:
    """Roles are fixed — 6 total, one per UserRole enum member."""
    existing = {r.name: r for r in db.query(Role).all()}
    descriptions = {
        UserRole.ADMIN: "System administrator",
        UserRole.SALES_OPS: "Sales operations manager",
        UserRole.SALES_REP: "Field sales representative",
        UserRole.MARKETING_OPS: "Marketing operations specialist",
        UserRole.SUPPORT_AGENT: "Support agent — exception resolution",
        UserRole.ANALYST: "Business analyst",
    }
    for role_name, desc in descriptions.items():
        if role_name not in existing:
            existing[role_name] = Role(name=role_name, description=desc)
            db.add(existing[role_name])
    db.flush()
    return existing


def _create_territories(db: Session) -> list[Territory]:
    territories = [
        Territory(
            code=SEQ_TERRITORY_CODE.next(),
            name="North America",
            region=TerritoryRegion.NORTH_AMERICA,
            postal_prefixes="0,1,2,3,4,5,6,7,8,9",
            is_active=True,
        ),
        Territory(
            code=SEQ_TERRITORY_CODE.next(),
            name="EMEA",
            region=TerritoryRegion.EMEA,
            postal_prefixes="",
            is_active=True,
        ),
        Territory(
            code=SEQ_TERRITORY_CODE.next(),
            name="APAC",
            region=TerritoryRegion.APAC,
            postal_prefixes="",
            is_active=True,
        ),
        Territory(
            code=SEQ_TERRITORY_CODE.next(),
            name="LATAM",
            region=TerritoryRegion.LATAM,
            postal_prefixes="",
            is_active=True,
        ),
    ]
    db.add_all(territories)
    db.flush()
    return territories


def _create_products(db: Session) -> list[Product]:
    """6 products — 2 per tier."""
    defs = [
        ("Starter CRM", ProductTier.BASIC, 99.00),
        ("Starter Automation", ProductTier.BASIC, 149.00),
        ("Pro Sales Suite", ProductTier.PRO, 599.00),
        ("Pro Marketing Suite", ProductTier.PRO, 749.00),
        ("Enterprise Platform", ProductTier.ENTERPRISE, 4999.00),
        ("Enterprise Analytics", ProductTier.ENTERPRISE, 7499.00),
    ]
    products = [
        Product(
            code=SEQ_PRODUCT_CODE.next(),
            name=name,
            tier=tier,
            list_price=price,
            is_active=True,
        )
        for name, tier, price in defs
    ]
    db.add_all(products)
    db.flush()
    return products


def _create_users(
    db: Session, roles: dict[UserRole, Role], fake: Faker, count: int,
) -> list[User]:
    """50 users — mostly sales_rep, plus a few of each other role."""
    role_assignment = (
        [UserRole.SALES_REP] * (count - 20)
        + [UserRole.SALES_OPS] * 4
        + [UserRole.MARKETING_OPS] * 4
        + [UserRole.SUPPORT_AGENT] * 5
        + [UserRole.ANALYST] * 3
        + [UserRole.ADMIN] * 4
    )[:count]

    users = []
    for role_name in role_assignment:
        first = fake.first_name()
        last = fake.last_name()
        users.append(
            User(
                business_id=SEQ_USER.next(),
                email=f"{first.lower()}.{last.lower()}.{len(users)}@leadflow-demo.io",
                full_name=f"{first} {last}",
                hashed_password="$2b$12$demo.not.a.real.hash",  # placeholder
                role_id=roles[role_name].id,
                is_active=True,
                last_login_at=datetime.now(timezone.utc) - timedelta(days=fake.random_int(0, 30)),
            )
        )
    db.add_all(users)
    db.flush()
    return users


def _create_sales_reps(
    db: Session,
    territories: list[Territory],
    products: list[Product],
    fake: Faker,
    count: int,
) -> list[SalesRep]:
    """Distribute reps across territories; assign product expertise."""
    reps = []
    capacity_min, capacity_max = cfg.SALES_REP_CAPACITY_RANGE
    for i in range(count):
        territory = territories[i % len(territories)]
        # Each rep specializes in 1–3 products (tier-aligned).
        n_products = fake.random_int(min=1, max=3)
        expertise_products = fake.random_elements(
            elements=products, length=n_products, unique=True,
        )
        reps.append(
            SalesRep(
                business_id=SEQ_REP.next(),
                full_name=fake.name(),
                email=f"rep{len(reps) + 1:04d}@leadflow-demo.io",
                territory_id=territory.id,
                product_expertise=",".join(p.code for p in expertise_products),
                workload_capacity=fake.random_int(min=capacity_min, max=capacity_max),
                current_workload=0,
                is_active=True,
                hired_on=fake.date_between(start_date="-5y", end_date="-30d"),
            )
        )
    db.add_all(reps)
    db.flush()
    return reps


def _create_campaigns(
    db: Session, fake: Faker, count: int,
) -> list[Campaign]:
    """20 campaigns across lead sources."""
    now = datetime.now(timezone.utc)
    sources = list(LeadSource)
    statuses = list(CampaignStatus)
    status_weights = [cfg.CAMPAIGN_STATUS_WEIGHTS[s.value] for s in statuses]

    campaigns = []
    for i in range(count):
        source = sources[i % len(sources)]
        status = weighted_choice(fake, statuses, status_weights)
        start = now - timedelta(days=fake.random_int(30, 365))
        end = None if status in (CampaignStatus.ACTIVE, CampaignStatus.DRAFT) \
            else start + timedelta(days=fake.random_int(30, 180))

        campaigns.append(
            Campaign(
                business_id=SEQ_CAMPAIGN.next(),
                name=f"{source.value.title().replace('_', ' ')} Q{(i % 4) + 1} 2026",
                source=source,
                status=status,
                start_date=start,
                end_date=end,
                budget_usd=fake.random_int(min=5000, max=150000),
                owner=fake.name(),
            )
        )
    db.add_all(campaigns)
    db.flush()
    return campaigns


def generate_master_data(db: Session, seed: int, volumes) -> dict:
    """
    Top-level entry: build all master/reference records.
    Returns a dict of created entity lists for downstream use.
    """
    fake = Faker()
    Faker.seed(seed)

    roles = _ensure_roles(db)
    territories = _create_territories(db)
    products = _create_products(db)
    users = _create_users(db, roles, fake, volumes.users)
    reps = _create_sales_reps(db, territories, products, fake, volumes.sales_reps)
    campaigns = _create_campaigns(db, fake, volumes.campaigns)

    db.commit()
    return {
        "roles": list(roles.values()),
        "territories": territories,
        "products": products,
        "users": users,
        "sales_reps": reps,
        "campaigns": campaigns,
    }

