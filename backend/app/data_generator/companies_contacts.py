"""
Companies + Contacts generator.

5,000 companies assigned to territories by region.
10,000 contacts (~2 per company) with realistic names/emails/titles.
"""
from __future__ import annotations

from faker import Faker

from backend.app.data_generator.utils import weighted_choice
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.ids import SEQ_COMPANY, SEQ_CONTACT
from backend.app.models.enums import TerritoryRegion
from backend.app.models.organization import Company, Contact, Territory


_COMPANY_SUFFIXES = [
    "Labs", "Systems", "Technologies", "Group", "Inc", "Corp", "Partners",
    "Dynamics", "Solutions", "Software", "Networks", "Digital", "Services",
    "Holdings", "Ventures", "Analytics", "Robotics", "Works", "Studios",
]

_INDUSTRY_NAMES = {
    "saas": "Software as a Service",
    "fintech": "Financial Technology",
    "healthcare": "Healthcare",
    "retail": "Retail",
    "manufacturing": "Manufacturing",
    "logistics": "Logistics",
    "education": "Education",
    "other": "Other",
}

_CONTACT_TITLES = [
    "CEO", "CTO", "CFO", "COO", "VP Sales", "VP Marketing", "VP Engineering",
    "Director of Sales", "Director of Marketing", "Head of Growth",
    "Product Manager", "Engineering Manager", "Sales Manager",
    "Marketing Manager", "Business Development Manager",
]


def _pick_region(fake: Faker) -> TerritoryRegion:
    regions = list(cfg.REGION_WEIGHTS.keys())
    weights = [cfg.REGION_WEIGHTS[r] for r in regions]
    region_str = weighted_choice(fake, regions, weights)
    return TerritoryRegion(region_str)


def _pick_industry(fake: Faker) -> str:
    industries = list(cfg.INDUSTRY_WEIGHTS.keys())
    weights = [cfg.INDUSTRY_WEIGHTS[i] for i in industries]
    return weighted_choice(fake, industries, weights)


def _country_for_region(region: TerritoryRegion, fake: Faker) -> str:
    countries = {
        TerritoryRegion.NORTH_AMERICA: ["US", "CA"],
        TerritoryRegion.EMEA: ["GB", "DE", "FR", "NL", "IE", "ES"],
        TerritoryRegion.APAC: ["AU", "JP", "SG", "IN", "NZ"],
        TerritoryRegion.LATAM: ["BR", "MX", "AR", "CO", "CL"],
    }[region]
    return fake.random_element(elements=countries)


def _postal_for_country(country: str, fake: Faker) -> str:
    if country == "US":
        return fake.zipcode()
    if country == "CA":
        return fake.postcode()
    if country == "GB":
        return fake.postcode()
    return fake.postcode()


def generate_companies(
    db: Session,
    territories: list[Territory],
    seed: int,
    count: int,
) -> list[Company]:
    """5,000 companies distributed across territories by region."""
    fake = Faker()
    Faker.seed(seed + 1)

    # Region → territory mapping
    region_to_territory = {t.region: t for t in territories}

    companies = []
    for _ in range(count):
        region = _pick_region(fake)
        territory = region_to_territory[region]
        industry_key = _pick_industry(fake)
        country = _country_for_region(region, fake)
        postal = _postal_for_country(country, fake)

        name = f"{fake.company().split()[0]} {fake.random_element(_COMPANY_SUFFIXES)}"
        # Ensure employee_count and revenue are sensible for industry
        emp = fake.random_int(min=10, max=5000)
        # Loose revenue model: ~$200k/employee, ±50%
        rev = emp * fake.random_int(min=100_000, max=300_000)

        companies.append(
            Company(
                business_id=SEQ_COMPANY.next(),
                name=name,
                industry=_INDUSTRY_NAMES[industry_key],
                employee_count=emp,
                annual_revenue_usd=rev,
                country=country,
                postal_code=postal,
                website=f"https://{fake.domain_name()}",
                territory_id=territory.id,
            )
        )

    db.add_all(companies)
    db.flush()
    return companies


def generate_contacts(
    db: Session,
    companies: list[Company],
    seed: int,
    target_count: int,
) -> list[Contact]:
    """
    ~2 contacts per company. If target_count < len(companies), we cap at
    one per company. If target_count > 2 * len(companies), we add more.
    """
    fake = Faker()
    Faker.seed(seed + 2)

    contacts: list[Contact] = []
    used_emails: set[str] = set()

    def make_contact(company: Company) -> Contact | None:
        first = fake.first_name()
        last = fake.last_name()
        # Ensure unique email
        for attempt in range(5):
            local = f"{first.lower()}.{last.lower()}"
            if attempt > 0:
                local = f"{local}{attempt}"
            email = f"{local}@{company.website.replace('https://', '').replace('www.', '')}"
            if email not in used_emails:
                used_emails.add(email)
                return Contact(
                    business_id=SEQ_CONTACT.next(),
                    company_id=company.id,
                    first_name=first,
                    last_name=last,
                    email=email,
                    phone=fake.phone_number()[:32] if fake.boolean(chance_of_getting_true=85) else None,
                    title=fake.random_element(elements=_CONTACT_TITLES),
                )
        return None  # extremely unlikely

    # First pass — 1 contact per company
    for company in companies:
        if len(contacts) >= target_count:
            break
        c = make_contact(company)
        if c:
            contacts.append(c)

    # Second pass — add a 2nd contact per company until we hit target
    if len(contacts) < target_count:
        for company in companies:
            if len(contacts) >= target_count:
                break
            c = make_contact(company)
            if c:
                contacts.append(c)

    db.add_all(contacts)
    db.flush()
    return contacts

