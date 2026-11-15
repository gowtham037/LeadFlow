"""
Opportunity endpoints.

GET  /api/opportunities                     — list with filters
GET  /api/opportunities/{business_id}       — detail with stage history
POST /api/opportunities/{business_id}/advance   — advance stage
POST /api/opportunities/{business_id}/close     — mark won/lost
GET  /api/opportunities/stats/summary       — KPI summary
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.engines.opportunity.engine import (
    InvalidStageTransition,
    advance_stage,
    close_lost,
    close_won,
)
from backend.app.models.enums import (
    LostReason,
    OpportunityStage,
    OpportunityStatus,
)
from backend.app.models.marketing import Lead
from backend.app.models.organization import Company, Contact, SalesRep
from backend.app.models.sales_ops import Opportunity, StageHistory
from backend.app.models.system import User


router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


class OpportunityListItem(BaseModel):
    id: int
    business_id: str
    name: str
    lead_business_id: str
    rep_name: str
    amount_usd: float
    stage: str
    status: str
    created_at: str
    closed_at: str | None


class OpportunityListResponse(BaseModel):
    items: list[OpportunityListItem]
    total: int
    page: int
    page_size: int
    pages: int


class StageHistoryItem(BaseModel):
    from_stage: str | None
    to_stage: str
    transitioned_at: str
    actor: str
    notes: str | None


class OpportunityDetail(BaseModel):
    id: int
    business_id: str
    name: str
    lead_business_id: str
    lead_id: int
    company_name: str | None
    contact_email: str | None
    rep: dict
    amount_usd: float
    stage: str
    status: str
    created_at: str
    closed_at: str | None
    won_reason: str | None
    lost_reason: str | None
    stage_history: list[StageHistoryItem]


class AdvanceRequest(BaseModel):
    to_stage: OpportunityStage
    notes: str | None = None


class CloseRequest(BaseModel):
    status: Literal["won", "lost"]
    won_reason: str | None = None
    lost_reason: LostReason | None = None


@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = Query(None),
    status: OpportunityStatus | None = None,
    stage: OpportunityStage | None = None,
    rep_id: int | None = None,
    sort_by: Literal["id", "amount", "created_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
) -> OpportunityListResponse:
    qry = db.query(Opportunity)
    if status:
        qry = qry.filter(Opportunity.status == status)
    if stage:
        qry = qry.filter(Opportunity.stage == stage)
    if rep_id is not None:
        qry = qry.filter(Opportunity.rep_id == rep_id)
    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(Opportunity.business_id.ilike(like), Opportunity.name.ilike(like)))

    sort_col = {
        "id": Opportunity.id,
        "amount": Opportunity.amount_usd,
        "created_at": Opportunity.created_at,
    }[sort_by]
    qry = qry.order_by(desc(sort_col) if order == "desc" else sort_col)

    total = qry.count()
    rows = qry.offset((page - 1) * page_size).limit(page_size).all()

    lead_ids = {r.lead_id for r in rows}
    rep_ids = {r.rep_id for r in rows}
    leads = {l.id: l for l in db.query(Lead).filter(Lead.id.in_(lead_ids)).all()}
    reps = {r.id: r for r in db.query(SalesRep).filter(SalesRep.id.in_(rep_ids)).all()}

    items = []
    for r in rows:
        lead = leads.get(r.lead_id)
        rep = reps.get(r.rep_id)
        items.append(OpportunityListItem(
            id=r.id,
            business_id=r.business_id,
            name=r.name,
            lead_business_id=lead.business_id if lead else "?",
            rep_name=rep.full_name if rep else "?",
            amount_usd=float(r.amount_usd),
            stage=r.stage.value,
            status=r.status.value,
            created_at=r.created_at.isoformat(),
            closed_at=r.closed_at.isoformat() if r.closed_at else None,
        ))

    return OpportunityListResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/stats/summary")
def opportunity_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    by_status = dict(
        db.query(Opportunity.status, func.count(Opportunity.id))
        .group_by(Opportunity.status).all()
    )
    by_stage = dict(
        db.query(Opportunity.stage, func.count(Opportunity.id))
        .filter(Opportunity.status == OpportunityStatus.OPEN)
        .group_by(Opportunity.stage).all()
    )
    pipeline = (
        db.query(func.coalesce(func.sum(Opportunity.amount_usd), 0))
        .filter(Opportunity.status == OpportunityStatus.OPEN).scalar() or 0
    )
    revenue = (
        db.query(func.coalesce(func.sum(Opportunity.amount_usd), 0))
        .filter(Opportunity.status == OpportunityStatus.WON).scalar() or 0
    )
    return {
        "total_opportunities": db.query(func.count(Opportunity.id)).scalar() or 0,
        "by_status": {k.value if hasattr(k, "value") else str(k): v for k, v in by_status.items()},
        "open_by_stage": {k.value if hasattr(k, "value") else str(k): v for k, v in by_stage.items()},
        "open_pipeline_value": float(pipeline),
        "won_revenue": float(revenue),
    }


@router.get("/{business_id}", response_model=OpportunityDetail)
def get_opportunity(
    business_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OpportunityDetail:
    opp = db.query(Opportunity).filter(Opportunity.business_id == business_id).one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {business_id} not found")

    lead = db.query(Lead).filter(Lead.id == opp.lead_id).one_or_none()
    rep = db.query(SalesRep).filter(SalesRep.id == opp.rep_id).one_or_none()
    company = db.query(Company).filter(Company.id == lead.company_id).one_or_none() if lead else None
    contact = db.query(Contact).filter(Contact.id == lead.contact_id).one_or_none() if lead else None

    history = (
        db.query(StageHistory)
        .filter(StageHistory.opportunity_id == opp.id)
        .order_by(StageHistory.transitioned_at.asc())
        .all()
    )

    return OpportunityDetail(
        id=opp.id,
        business_id=opp.business_id,
        name=opp.name,
        lead_business_id=lead.business_id if lead else "?",
        lead_id=opp.lead_id,
        company_name=company.name if company else None,
        contact_email=contact.email if contact else None,
        rep={"id": rep.id, "full_name": rep.full_name, "email": rep.email} if rep else {"id": None, "full_name": "?", "email": "?"},
        amount_usd=float(opp.amount_usd),
        stage=opp.stage.value,
        status=opp.status.value,
        created_at=opp.created_at.isoformat(),
        closed_at=opp.closed_at.isoformat() if opp.closed_at else None,
        won_reason=opp.won_reason,
        lost_reason=opp.lost_reason.value if opp.lost_reason else None,
        stage_history=[
            StageHistoryItem(
                from_stage=h.from_stage.value if h.from_stage else None,
                to_stage=h.to_stage.value,
                transitioned_at=h.transitioned_at.isoformat(),
                actor=h.actor,
                notes=h.notes,
            )
            for h in history
        ],
    )


@router.post("/{business_id}/advance", response_model=OpportunityDetail)
def advance_opp(
    business_id: str,
    body: AdvanceRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OpportunityDetail:
    opp = db.query(Opportunity).filter(Opportunity.business_id == business_id).one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {business_id} not found")

    try:
        advance_stage(db, opp, body.to_stage, actor=f"user:{user.business_id}", notes=body.notes)
        db.commit()
    except (InvalidStageTransition, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_opportunity(business_id, db=db, _user=user)


@router.post("/{business_id}/close", response_model=OpportunityDetail)
def close_opp(
    business_id: str,
    body: CloseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OpportunityDetail:
    opp = db.query(Opportunity).filter(Opportunity.business_id == business_id).one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {business_id} not found")

    try:
        if body.status == "won":
            close_won(db, opp, won_reason=body.won_reason, actor=f"user:{user.business_id}")
        else:
            if body.lost_reason is None:
                raise ValueError("lost_reason required when closing as lost")
            close_lost(db, opp, body.lost_reason, actor=f"user:{user.business_id}")
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_opportunity(business_id, db=db, _user=user)

