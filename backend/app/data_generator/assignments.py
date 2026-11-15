"""
Assignment history generator — one immutable row per lead that has an
assigned_rep_id set.

Mirrors what the routing engine writes at runtime, so the UI shows real
assignment history from day one. Each row captures: reason, eligible reps,
workload at assignment.
"""
from __future__ import annotations

import json
from datetime import timedelta

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.models.enums import AssignmentReason, LeadStatus
from backend.app.models.marketing import Lead
from backend.app.models.organization import Product, SalesRep
from backend.app.models.sales_ops import LeadAssignmentHistory


def generate_assignment_history(
    db: Session,
    leads: list[Lead],
    sales_reps: list[SalesRep],
    products: list[Product],
    seed: int,
) -> list[LeadAssignmentHistory]:
    fake = Faker()
    Faker.seed(seed + 7)

    reps_by_territory: dict[int, list[SalesRep]] = {}
    for r in sales_reps:
        reps_by_territory.setdefault(r.territory_id, []).append(r)

    rows: list[LeadAssignmentHistory] = []
    for lead in leads:
        if lead.assigned_rep_id is None:
            continue

        # Determine reason based on whether rep's expertise matches lead's interest
        rep = next((r for r in sales_reps if r.id == lead.assigned_rep_id), None)
        if not rep:
            continue
        rep_products = set(rep.product_expertise.split(","))
        lead_products = set(lead.product_interest.split(","))
        matched = rep_products & lead_products

        if matched and rep.territory_id == lead.territory_id:
            reason = AssignmentReason.TERRITORY_PRODUCT_MATCH
        elif rep.territory_id == lead.territory_id:
            reason = AssignmentReason.TERRITORY_ONLY
        elif matched:
            reason = AssignmentReason.PRODUCT_ONLY
        else:
            reason = AssignmentReason.WORKLOAD_BALANCE

        eligible = reps_by_territory.get(lead.territory_id, [])
        eligible_payload = [
            {
                "rep_id": r.id,
                "workload": r.current_workload,
                "capacity": r.workload_capacity,
                "matched_on": (
                    "territory+product"
                    if set(r.product_expertise.split(",")) & lead_products
                    else "territory"
                ),
            }
            for r in eligible
        ]

        rows.append(
            LeadAssignmentHistory(
                lead_id=lead.id,
                assigned_rep_id=lead.assigned_rep_id,
                assigned_at=lead.assigned_at or lead.created_at,
                reason=reason,
                territory_considered=lead.territory_id,
                product_required=lead.product_interest,
                eligible_reps_json=json.dumps(eligible_payload),
                decision_notes=f"Auto-routed to {rep.full_name} (reason: {reason.value})",
                workload_at_assignment=rep.current_workload,
            )
        )

    db.add_all(rows)
    db.flush()
    return rows

