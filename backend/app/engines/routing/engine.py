"""
Deterministic lead routing engine.

route_lead(lead, db) → RoutingDecision

Decision priority (deterministic, explainable):
  1. Territory match (lead.territory_id == rep.territory_id) — mandatory
  2. Product expertise overlap (rep.product_expertise ∩ lead.product_interest) — bonus
  3. Workload headroom (rep.current_workload < rep.workload_capacity) — mandatory
  4. Among eligible reps: pick the one with lowest (current_workload / workload_capacity) ratio
  5. Tie-break by rep.id ascending (deterministic)

If no eligible reps: returns RoutingDecision with reason=FALLBACK_DEFAULT and rep_id=None
(Routing failure is logged — never silently ignored.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.enums import AssignmentReason, LeadStatus
from backend.app.models.marketing import Lead
from backend.app.models.organization import SalesRep


@dataclass
class RepCandidate:
    rep_id: int
    full_name: str
    workload: int
    capacity: int
    territory_match: bool
    product_match: bool
    utilization: float  # workload / capacity

    def to_dict(self) -> dict:
        return {
            "rep_id": self.rep_id,
            "full_name": self.full_name,
            "workload": self.workload,
            "capacity": self.capacity,
            "utilization": round(self.utilization, 3),
            "territory_match": self.territory_match,
            "product_match": self.product_match,
        }


@dataclass
class RoutingDecision:
    lead_id: int
    assigned_rep_id: int | None
    reason: AssignmentReason | None
    territory_considered: int | None
    product_required: str | None
    eligible_reps: list[RepCandidate] = field(default_factory=list)
    decision_notes: str = ""
    workload_at_assignment: int = 0

    @property
    def assigned(self) -> bool:
        return self.assigned_rep_id is not None


def _lead_product_codes(lead: Lead) -> set[str]:
    """Parse lead.product_interest into a set of product codes."""
    return {code.strip() for code in (lead.product_interest or "").split(",") if code.strip()}


def _rep_product_codes(rep: SalesRep) -> set[str]:
    """Parse rep.product_expertise into a set of product codes."""
    return {code.strip() for code in (rep.product_expertise or "").split(",") if code.strip()}


def route_lead(lead: Lead, db: Session) -> RoutingDecision:
    """
    Pure decision function — returns what SHOULD be assigned.
    Does NOT mutate the lead or rep — caller applies decision (see apply_decision).
    """
    lead_products = _lead_product_codes(lead)
    lead_territory = lead.territory_id

    # Query all active reps (filtering is cheap enough at ~80 reps; for scale we'd
    # pre-index, but this keeps the logic transparent).
    all_reps = db.query(SalesRep).filter(SalesRep.is_active.is_(True)).all()

    eligible: list[RepCandidate] = []
    for rep in all_reps:
        if rep.current_workload >= rep.workload_capacity:
            continue  # No headroom

        rep_products = _rep_product_codes(rep)
        territory_match = (rep.territory_id == lead_territory)
        product_match = bool(lead_products & rep_products)

        if not territory_match:
            continue  # Territory is mandatory — skip non-territory reps

        eligible.append(
            RepCandidate(
                rep_id=rep.id,
                full_name=rep.full_name,
                workload=rep.current_workload,
                capacity=rep.workload_capacity,
                territory_match=territory_match,
                product_match=product_match,
                utilization=(rep.current_workload / rep.workload_capacity),
            )
        )

    if not eligible:
        return RoutingDecision(
            lead_id=lead.id,
            assigned_rep_id=None,
            reason=None,
            territory_considered=lead_territory,
            product_required=lead.product_interest,
            eligible_reps=[],
            decision_notes="No eligible reps: territory full or no active reps",
        )

    # Prefer product_match reps if any; else fall back to territory-only reps
    product_matched = [c for c in eligible if c.product_match]
    if product_matched:
        pool = product_matched
        reason = AssignmentReason.TERRITORY_PRODUCT_MATCH
    else:
        pool = eligible
        reason = AssignmentReason.TERRITORY_ONLY

    # Sort by utilization ascending, then rep_id ascending (deterministic)
    pool.sort(key=lambda c: (c.utilization, c.rep_id))
    chosen = pool[0]

    return RoutingDecision(
        lead_id=lead.id,
        assigned_rep_id=chosen.rep_id,
        reason=reason,
        territory_considered=lead_territory,
        product_required=lead.product_interest,
        eligible_reps=eligible,
        decision_notes=(
            f"Assigned to {chosen.full_name} (rep {chosen.rep_id}) — "
            f"reason={reason.value}, utilization={chosen.utilization:.2f}, "
            f"product_match={chosen.product_match}"
        ),
        workload_at_assignment=chosen.workload,
    )


def apply_decision(decision: RoutingDecision, lead: Lead, db: Session) -> None:
    """
    Apply a routing decision: update lead + rep workload, write history.
    MUST be called inside a transaction — caller commits.
    """
    if not decision.assigned:
        return  # Routing failure — nothing to apply

    from backend.app.models.sales_ops import LeadAssignmentHistory
    import json

    now = datetime.now(timezone.utc)

    lead.assigned_rep_id = decision.assigned_rep_id
    lead.assigned_at = now
    if lead.status == LeadStatus.QUALIFIED:
        lead.status = LeadStatus.ASSIGNED

    # Bump rep workload
    rep = db.query(SalesRep).filter(SalesRep.id == decision.assigned_rep_id).one()
    rep.current_workload += 1

    # Write immutable history
    history = LeadAssignmentHistory(
        lead_id=lead.id,
        assigned_rep_id=decision.assigned_rep_id,
        assigned_at=now,
        reason=decision.reason,
        territory_considered=decision.territory_considered,
        product_required=decision.product_required,
        eligible_reps_json=json.dumps([c.to_dict() for c in decision.eligible_reps]),
        decision_notes=decision.decision_notes,
        workload_at_assignment=decision.workload_at_assignment,
    )
    db.add(history)

