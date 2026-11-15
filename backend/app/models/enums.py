"""
All business enumerations.

Backed by Python enums + native Postgres enum types via SQLAlchemy Enum.
19 enums total, locked by accepted defaults (see DESIGN_DECISIONS.md).
"""
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    SALES_OPS = "sales_ops"
    SALES_REP = "sales_rep"
    MARKETING_OPS = "marketing_ops"
    SUPPORT_AGENT = "support_agent"
    ANALYST = "analyst"


class LeadStatus(str, Enum):
    NEW = "new"
    SCORED = "scored"
    QUALIFIED = "qualified"
    ASSIGNED = "assigned"
    WORKING = "working"
    CONVERTED = "converted"
    DISQUALIFIED = "disqualified"
    RECYCLED = "recycled"


class LeadSource(str, Enum):
    WEBINAR = "webinar"
    CONTENT_DOWNLOAD = "content_download"
    PAID_AD = "paid_ad"
    EVENT = "event"
    PARTNER_REFERRAL = "partner_referral"
    OUTBOUND = "outbound"
    INBOUND_FORM = "inbound_form"


class ScoreCategory(str, Enum):
    HOT = "hot"
    WARM = "warm"
    NURTURE = "nurture"
    COLD = "cold"


class ConsentChannel(str, Enum):
    """A1: per-channel consent."""
    EMAIL = "email"
    PHONE = "phone"
    SMS = "sms"
    MARKETING = "marketing"


class ConsentStatus(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    PENDING = "pending"


class ActivityType(str, Enum):
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"
    WEB_VISIT = "web_visit"
    DEMO_REQUEST = "demo_request"
    CONTENT_DOWNLOAD = "content_download"
    CALL = "call"
    MEETING = "meeting"


class TaskPriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class OpportunityStage(str, Enum):
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED = "closed"


class OpportunityStatus(str, Enum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"


class LostReason(str, Enum):
    """U7: locked lost-reason taxonomy."""
    PRICE = "price"
    TIMING = "timing"
    COMPETITOR = "competitor"
    NO_BUDGET = "no_budget"
    NO_RESPONSE = "no_response"
    OTHER = "other"


class ExceptionType(str, Enum):
    OPTOUT_CONTACTED = "optout_contacted"
    POST_CONVERSION_SCORING = "post_conversion_scoring"
    TERRITORY_MISMATCH = "territory_mismatch"
    DUPLICATE_OPPORTUNITY = "duplicate_opportunity"
    STAGE_GAP = "stage_gap"


class ExceptionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AssignmentReason(str, Enum):
    TERRITORY_PRODUCT_MATCH = "territory_product_match"
    TERRITORY_ONLY = "territory_only"
    PRODUCT_ONLY = "product_only"
    WORKLOAD_BALANCE = "workload_balance"
    FALLBACK_DEFAULT = "fallback_default"


class TerritoryRegion(str, Enum):
    NORTH_AMERICA = "north_america"
    EMEA = "emea"
    APAC = "apac"
    LATAM = "latam"


class ProductTier(str, Enum):
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"

