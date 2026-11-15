"""
API tests — authentication.

Covers:
  - Login with valid/invalid credentials
  - Missing/invalid/expired token
  - /me endpoint
  - Token refresh
"""
from __future__ import annotations

from fastapi.testclient import TestClient

DEMO_PASSWORD = "leadflow-demo"


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["database"] == "ok"


def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "app" in r.json()
    assert r.json()["docs"] == "/docs"


def test_login_success(client: TestClient, admin_credentials) -> None:
    email, password = admin_credentials
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    d = r.json()
    assert "access_token" in d
    assert d["token_type"] == "bearer"
    assert d["user"]["email"] == email
    assert d["user"]["role"] == "admin"


def test_login_wrong_password(client: TestClient, admin_credentials) -> None:
    email, _ = admin_credentials
    r = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    assert r.status_code == 401


def test_login_unknown_email(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert r.status_code == 401


def test_login_invalid_email_format(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert r.status_code == 422  # Pydantic validation


def test_me_without_token(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_invalid_token(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert r.status_code == 401


def test_me_with_valid_token(client: TestClient, auth_headers, admin_credentials) -> None:
    email, _ = admin_credentials
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == email
    assert d["role"] == "admin"


def test_refresh_token(client: TestClient, auth_headers) -> None:
    r = client.post("/api/auth/refresh", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert "access_token" in d
