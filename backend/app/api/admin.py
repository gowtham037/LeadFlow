"""
Admin endpoints — run engines from the API.

POST /api/admin/seed              — wipe + regenerate full dataset
POST /api/admin/rescore           — re-score all baseline leads
POST /api/admin/route             — route all qualified leads
POST /api/admin/tasks             — generate tasks for all assigned leads
POST /api/admin/opportunities     — convert all CONVERTED leads missing opps
GET  /api/admin/validate          — run full validation report
GET  /api/admin/pipeline-stats    — quick operational metrics

All POST endpoints require role=admin or sales_ops.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_role
from backend.app.models.system import User
from backend.app.validation import run_all_checks


logger = logging.getLogger("api.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


class SeedRequest(BaseModel):
    mode: str = "full"  # "starter" or "full"
    seed: int = 20261022


class AdminActionResponse(BaseModel):
    status: str
    message: str
    result: dict | None = None


# ---------- POST /seed ----------

@router.post("/seed", response_model=AdminActionResponse)
def trigger_seed(
    body: SeedRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "sales_ops")),
) -> AdminActionResponse:
    """Wipe + regenerate the synthetic dataset (full or starter)."""
    from backend.app.data_generator.generate import run

    if body.mode not in ("starter", "full"):
        raise HTTPException(status_code=400, detail="mode must be 'starter' or 'full'")

    try:
        counts = run(mode=body.mode, seed=body.seed)
        return AdminActionResponse(
            status="ok",
            message=f"Seeded {body.mode} dataset (seed={body.seed})",
            result=counts,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Seed failed: {exc}") from exc


# ---------- POST /rescore ----------

@router.post("/rescore", response_model=AdminActionResponse)
def trigger_rescore(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "sales_ops")),
) -> AdminActionResponse:
    from backend.app.engines.scoring.runner import rescore_all_leads

    try:
        n = rescore_all_leads(db)
        return AdminActionResponse(
            status="ok",
            message=f"Rescored {n} leads",
            result={"scored": n},
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Rescore failed: {exc}") from exc


# ---------- POST /route ----------

@router.post("/route", response_model=AdminActionResponse)
def trigger_routing(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "sales_ops")),
) -> AdminActionResponse:
    from backend.app.engines.routing.runner import route_all_qualified_leads

    try:
        summary = route_all_qualified_leads(db)
        return AdminActionResponse(
            status="ok",
            message=f"Routed {summary.get('assigned', 0)} leads "
                    f"({summary.get('unroutable', 0)} unroutable)",
            result=summary,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Routing failed: {exc}") from exc


# ---------- POST /tasks ----------

@router.post("/tasks", response_model=AdminActionResponse)
def trigger_tasks(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "sales_ops")),
) -> AdminActionResponse:
    from backend.app.engines.task_management.runner import generate_all_followup_tasks

    try:
        summary = generate_all_followup_tasks(db)
        return AdminActionResponse(
            status="ok",
            message=f"Created {summary.get('created', 0)} follow-up tasks",
            result=summary,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Task generation failed: {exc}") from exc


# ---------- POST /opportunities ----------

@router.post("/opportunities", response_model=AdminActionResponse)
def trigger_opportunities(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "sales_ops")),
) -> AdminActionResponse:
    from backend.app.engines.opportunity.runner import convert_all_eligible_leads

    try:
        summary = convert_all_eligible_leads(db)
        return AdminActionResponse(
            status="ok",
            message=f"Created {summary.get('created', 0)} opportunities",
            result=summary,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Opportunity generation failed: {exc}") from exc


# ---------- GET /validate ----------

@router.get("/validate")
def run_validation(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Full data-quality validation report."""
    report = run_all_checks(db)
    return report.to_dict()


# ---------- GET /pipeline-stats ----------

@router.get("/pipeline-stats")
def pipeline_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Quick operational counts for a dashboard widget."""
    from sqlalchemy import func
    from backend.app.models.marketing import Lead, Activity, Consent
    from backend.app.models.sales_ops import Task, Opportunity
    from backend.app.models.system import ExceptionRecord

    return {
        "leads": db.query(func.count(Lead.id)).filter(Lead.is_baseline.is_(True)).scalar() or 0,
        "activities": db.query(func.count(Activity.id)).scalar() or 0,
        "consents": db.query(func.count(Consent.id)).scalar() or 0,
        "tasks": db.query(func.count(Task.id)).scalar() or 0,
        "opportunities": db.query(func.count(Opportunity.id)).scalar() or 0,
        "exceptions": db.query(func.count(ExceptionRecord.id)).scalar() or 0,
    }

