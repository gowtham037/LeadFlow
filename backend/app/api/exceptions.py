"""
Exception (anomaly) endpoints — surfaces the 5 injected anomalies + any
data-quality issues detected at runtime.

GET   /api/exceptions                  — list with filters
GET   /api/exceptions/{business_id}    — detail
PATCH /api/exceptions/{business_id}    — update status / resolution
GET   /api/exceptions/stats/summary    — by type/severity/status
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.enums import ExceptionSeverity, ExceptionStatus, ExceptionType
from backend.app.models.system import ExceptionRecord, User


router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


class ExceptionItem(BaseModel):
    id: int
    business_id: str
    entity_type: str
    entity_id: str
    issue_type: str
    severity: str
    status: str
    detected_at: str
    expected_behavior: str
    actual_behavior: str
    ground_truth_class: str | None
    resolved_at: str | None
    resolution_details: str | None


class ExceptionListResponse(BaseModel):
    items: list[ExceptionItem]
    total: int
    page: int
    page_size: int
    pages: int


class ResolveRequest(BaseModel):
    status: Literal["investigating", "resolved", "dismissed"]
    resolution_details: str | None = None


@router.get("", response_model=ExceptionListResponse)
def list_exceptions(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: ExceptionStatus | None = None,
    severity: ExceptionSeverity | None = None,
    issue_type: ExceptionType | None = None,
) -> ExceptionListResponse:
    qry = db.query(ExceptionRecord)
    if status:
        qry = qry.filter(ExceptionRecord.status == status)
    if severity:
        qry = qry.filter(ExceptionRecord.severity == severity)
    if issue_type:
        qry = qry.filter(ExceptionRecord.issue_type == issue_type)
    qry = qry.order_by(desc(ExceptionRecord.detected_at))

    total = qry.count()
    rows = qry.offset((page - 1) * page_size).limit(page_size).all()

    return ExceptionListResponse(
        items=[
            ExceptionItem(
                id=r.id,
                business_id=r.business_id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                issue_type=r.issue_type.value,
                severity=r.severity.value,
                status=r.status.value,
                detected_at=r.detected_at.isoformat(),
                expected_behavior=r.expected_behavior,
                actual_behavior=r.actual_behavior,
                ground_truth_class=r.ground_truth_class,
                resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
                resolution_details=r.resolution_details,
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/stats/summary")
def exception_summary(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> dict:
    by_type = dict(
        db.query(ExceptionRecord.issue_type, func.count(ExceptionRecord.id))
        .group_by(ExceptionRecord.issue_type).all()
    )
    by_severity = dict(
        db.query(ExceptionRecord.severity, func.count(ExceptionRecord.id))
        .group_by(ExceptionRecord.severity).all()
    )
    by_status = dict(
        db.query(ExceptionRecord.status, func.count(ExceptionRecord.id))
        .group_by(ExceptionRecord.status).all()
    )
    return {
        "total": db.query(func.count(ExceptionRecord.id)).scalar() or 0,
        "by_type": {k.value if hasattr(k, "value") else str(k): v for k, v in by_type.items()},
        "by_severity": {k.value if hasattr(k, "value") else str(k): v for k, v in by_severity.items()},
        "by_status": {k.value if hasattr(k, "value") else str(k): v for k, v in by_status.items()},
    }


@router.get("/{business_id}", response_model=ExceptionItem)
def get_exception(
    business_id: str,
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> ExceptionItem:
    r = db.query(ExceptionRecord).filter(ExceptionRecord.business_id == business_id).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail=f"Exception {business_id} not found")
    return ExceptionItem(
        id=r.id, business_id=r.business_id, entity_type=r.entity_type, entity_id=r.entity_id,
        issue_type=r.issue_type.value, severity=r.severity.value, status=r.status.value,
        detected_at=r.detected_at.isoformat(),
        expected_behavior=r.expected_behavior, actual_behavior=r.actual_behavior,
        ground_truth_class=r.ground_truth_class,
        resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
        resolution_details=r.resolution_details,
    )


@router.patch("/{business_id}", response_model=ExceptionItem)
def resolve_exception(
    business_id: str,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExceptionItem:
    from datetime import datetime, timezone
    r = db.query(ExceptionRecord).filter(ExceptionRecord.business_id == business_id).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail=f"Exception {business_id} not found")

    r.status = ExceptionStatus(body.status)
    if body.status in ("resolved", "dismissed"):
        r.resolved_at = datetime.now(timezone.utc)
        r.resolved_by = user.business_id
    r.resolution_details = body.resolution_details
    db.commit()

    return get_exception(business_id, db=db, _u=user)

