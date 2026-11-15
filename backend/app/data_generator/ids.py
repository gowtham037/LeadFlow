"""
Deterministic business-ID factory.

Formats (from spec):
  CO-000001            Company
  CON-000001           Contact
  LEAD-2026-000001     Lead
  ACT-<lead>-001       Activity (per-lead sequence)
  OPP-2026-000001      Opportunity
  TASK-<lead>-001      Task (per-lead sequence)
  CONSENT-<lead>-<n>   Consent (per-lead sequence)
  REP-0001             Sales Rep
  CMP-0001             Campaign
  USR-0001             User
  DUP-000001           Duplicate Group
  EXC-2026-000001      Exception Record
  PRD-0001             Product (in product.code)
  TER-0001             Territory (in territory.code)

All sequences reset when generate.py runs from scratch, ensuring bit-for-bit
reproducibility across runs on fresh databases.
"""
from itertools import count
from typing import Iterator


class IdSequence:
    """Thread-safe-enough for single-threaded generation. Not for concurrent use."""

    def __init__(self, prefix: str, width: int = 6, year: str | None = None,
                 separator: str = "-"):
        self.prefix = prefix
        self.width = width
        self.year = year
        self.separator = separator
        self._counter: Iterator[int] = count(1)

    def next(self) -> str:
        n = next(self._counter)
        if self.year:
            return f"{self.prefix}{self.separator}{self.year}{self.separator}{n:0{self.width}d}"
        return f"{self.prefix}{self.separator}{n:0{self.width}d}"

    def reset(self) -> None:
        self._counter = count(1)


# --- Module-level singleton sequences (reset by generator at start of each run) ---
SEQ_COMPANY = IdSequence("CO", width=6)
SEQ_CONTACT = IdSequence("CON", width=6)
SEQ_LEAD = IdSequence("LEAD", width=6, year="2026")
SEQ_OPP = IdSequence("OPP", width=6, year="2026")
SEQ_REP = IdSequence("REP", width=4)
SEQ_CAMPAIGN = IdSequence("CMP", width=4)
SEQ_USER = IdSequence("USR", width=4)
SEQ_DUP = IdSequence("DUP", width=6)
SEQ_EXCEPTION = IdSequence("EXC", width=6, year="2026")
SEQ_PRODUCT_CODE = IdSequence("PRD", width=4)
SEQ_TERRITORY_CODE = IdSequence("TER", width=4)


def activity_id(lead_business_id: str, seq: int) -> str:
    """ACT-<lead>-<seq>, e.g. ACT-LEAD-2026-000123-001"""
    return f"ACT-{lead_business_id}-{seq:03d}"


def task_id(lead_business_id: str, seq: int) -> str:
    """TASK-<lead>-<seq>"""
    return f"TASK-{lead_business_id}-{seq:03d}"


def consent_id(lead_business_id: str, seq: int) -> str:
    """CONSENT-<lead>-<seq>"""
    return f"CONSENT-{lead_business_id}-{seq:03d}"


def reset_all() -> None:
    """Reset all module-level sequences. Called by generate.py at start."""
    for seq in (
        SEQ_COMPANY, SEQ_CONTACT, SEQ_LEAD, SEQ_OPP, SEQ_REP, SEQ_CAMPAIGN,
        SEQ_USER, SEQ_DUP, SEQ_EXCEPTION, SEQ_PRODUCT_CODE, SEQ_TERRITORY_CODE,
    ):
        seq.reset()

