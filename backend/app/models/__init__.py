"""
Model registry — imports every ORM class so SQLAlchemy metadata is complete.
Alembic autogenerate and Base.metadata.create_all() both rely on these imports
being executed at package import time.
"""
from backend.app.models.base import TimestampMixin, utcnow
from backend.app.models.enums import *  # noqa: F401,F403
from backend.app.models.organization import (
    Company,
    Contact,
    Product,
    SalesRep,
    Territory,
)
from backend.app.models.marketing import (
    Activity,
    Campaign,
    Consent,
    Lead,
    LeadCampaign,
)
from backend.app.models.scoring import LeadScoreHistory, ScoreRule
from backend.app.models.sales_ops import (
    DuplicateGroup,
    LeadAssignmentHistory,
    Opportunity,
    StageHistory,
    Task,
)
from backend.app.models.system import AuditLog, ExceptionRecord, Role, User

__all__ = [
    "TimestampMixin", "utcnow",
    # organization
    "Company", "Contact", "Product", "SalesRep", "Territory",
    # marketing
    "Activity", "Campaign", "Consent", "Lead", "LeadCampaign",
    # scoring
    "LeadScoreHistory", "ScoreRule",
    # sales ops
    "DuplicateGroup", "LeadAssignmentHistory", "Opportunity", "StageHistory", "Task",
    # system
    "AuditLog", "ExceptionRecord", "Role", "User",
]

