"""Opportunity engine package exports."""
from backend.app.engines.opportunity.engine import (
    STAGE_ORDER,
    DuplicateOpportunity,
    InvalidStageTransition,
    OpportunityCreated,
    advance_stage,
    close_lost,
    close_won,
    create_opportunity,
)
from backend.app.engines.opportunity.runner import convert_all_eligible_leads

__all__ = [
    "STAGE_ORDER",
    "DuplicateOpportunity",
    "InvalidStageTransition",
    "OpportunityCreated",
    "advance_stage",
    "close_lost",
    "close_won",
    "create_opportunity",
    "convert_all_eligible_leads",
]

