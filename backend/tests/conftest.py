"""
Shared pytest fixtures for API tests.

These tests hit the REAL database (Postgres) — same DB the app uses. They
are NOT isolated (no transaction rollback per test) because we want to test
the actual production data. Each test cleans up after itself where needed.

Run with:
    PYTHONPATH=. python3 -m pytest backend/tests/test_api.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

DEMO_PASSWORD = "leadflow-demo"


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def admin_credentials(client: TestClient) -> tuple[str, str]:
    """Find any admin user's email + return (email, password)."""
    from backend.app.database import SessionLocal
    from backend.app.models.system import User, Role

    db = SessionLocal()
    try:
        admin = (
            db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(Role.name == "ADMIN", User.is_active.is_(True))
            .first()
        )
        if not admin:
            pytest.skip("No admin user in DB — run './run-local.sh seed full' first")
        return admin.email, DEMO_PASSWORD
    finally:
        db.close()


@pytest.fixture(scope="session")
def admin_token(client: TestClient, admin_credentials: tuple[str, str]) -> str:
    email, password = admin_credentials
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
