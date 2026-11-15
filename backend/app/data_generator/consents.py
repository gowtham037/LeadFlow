"""
Consent generator — one row per (lead, channel) per change.

Baseline: ~95% grant email, ~88% phone, ~75% sms, ~90% marketing.
Small slice opted out (CONSENT_GRANTED_RATES complement).

A1: per-channel. If a lead is opted out of email, no email tasks are ever
created for that lead. This is validated by the task engine later.
"""
from __future__ import annotations

from datetime import timedelta

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.ids import consent_id
from backend.app.models.enums import ConsentChannel, ConsentStatus
from backend.app.models.marketing import Consent, Lead


_CHANNELS = [
    ConsentChannel.EMAIL,
    ConsentChannel.PHONE,
    ConsentChannel.SMS,
    ConsentChannel.MARKETING,
]


def generate_consents(
    db: Session,
    leads: list[Lead],
    seed: int,
) -> list[Consent]:
    fake = Faker()
    Faker.seed(seed + 5)

    consents: list[Consent] = []
    for lead in leads:
        base = lead.created_at
        for seq, channel in enumerate(_CHANNELS, start=1):
            granted_prob = cfg.CONSENT_GRANTED_RATES.get(channel.value, 0.9)
            status = (
                ConsentStatus.GRANTED
                if fake.random.random() < granted_prob
                else ConsentStatus.REVOKED
            )
            consents.append(
                Consent(
                    business_id=consent_id(lead.business_id, seq),
                    lead_id=lead.id,
                    channel=channel,
                    status=status,
                    changed_at=base + timedelta(hours=fake.random_int(min=1, max=48)),
                    reason=None if status == ConsentStatus.GRANTED else "opt_out_form",
                )
            )

    db.add_all(consents)
    db.flush()
    return consents

