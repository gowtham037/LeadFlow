"""
Main API router — composes all sub-routers.

Imported by backend/app/main.py and mounted at /.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.admin import router as admin_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.auth import router as auth_router
from backend.app.api.exceptions import router as exceptions_router
from backend.app.api.leads import router as leads_router
from backend.app.api.opportunities import router as opportunities_router


api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(leads_router)
api_router.include_router(opportunities_router)
api_router.include_router(analytics_router)
api_router.include_router(exceptions_router)
api_router.include_router(admin_router)
