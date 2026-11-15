"""
API tests — leads.

Covers:
  - List with pagination, filters, search, sort
  - Detail lookup (found / not found)
  - Score detail with feature contributions
  - Consent status
  - RBAC (auth required)
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_leads_auth_required(client: TestClient) -> None:
    r = client.get("/api/leads")
    assert r.status_code == 401


def test_list_leads_basic(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads?page_size=5", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d
    assert d["page"] == 1
    assert d["page_size"] == 5
    assert len(d["items"]) <= 5
    assert d["total"] > 0


def test_list_leads_pagination(client: TestClient, auth_headers) -> None:
    r1 = client.get("/api/leads?page=1&page_size=3", headers=auth_headers)
    r2 = client.get("/api/leads?page=2&page_size=3", headers=auth_headers)
    assert r1.status_code == r2.status_code == 200
    ids_1 = {x["business_id"] for x in r1.json()["items"]}
    ids_2 = {x["business_id"] for x in r2.json()["items"]}
    assert ids_1.isdisjoint(ids_2), "Pages must not overlap"


def test_list_leads_filter_by_category(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads?category=hot&page_size=10", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    for item in d["items"]:
        assert item["current_score_category"] == "hot"


def test_list_leads_filter_by_status(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads?status=converted&page_size=10", headers=auth_headers)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "converted"


def test_list_leads_invalid_category_400(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads?category=nonsense", headers=auth_headers)
    assert r.status_code == 422  # enum validation


def test_list_leads_sort_by_score(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads?sort_by=score&order=desc&page_size=5", headers=auth_headers)
    assert r.status_code == 200
    scores = [i["current_score"] for i in r.json()["items"] if i["current_score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_list_leads_search(client: TestClient, auth_headers) -> None:
    # First get a known business ID
    r = client.get("/api/leads?page_size=1", headers=auth_headers)
    sample = r.json()["items"][0]["business_id"]

    # Search for it
    r2 = client.get(f"/api/leads?q={sample}", headers=auth_headers)
    assert r2.status_code == 200
    d = r2.json()
    assert d["total"] >= 1
    assert any(i["business_id"] == sample for i in d["items"])


def test_lead_summary(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads/stats/summary", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["total_leads"] > 0
    assert "by_category" in d
    assert "by_status" in d


def test_get_lead_detail(client: TestClient, auth_headers) -> None:
    # Get any lead business ID
    r = client.get("/api/leads?category=hot&page_size=1", headers=auth_headers)
    sample_id = r.json()["items"][0]["business_id"]

    r2 = client.get(f"/api/leads/{sample_id}", headers=auth_headers)
    assert r2.status_code == 200
    d = r2.json()
    assert d["business_id"] == sample_id
    assert d["current_score_category"] == "hot"
    assert "company" in d
    assert "contact" in d
    assert "score_detail" in d
    # Score detail must have contributions
    if d["score_detail"]:
        assert d["score_detail"]["total"] == d["score_detail"]["fit"] + d["score_detail"]["intent"] + d["score_detail"]["engagement"] + d["score_detail"]["recency"]
        assert len(d["score_detail"]["contributions"]) == 12


def test_get_lead_404(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads/LEAD-2026-999999", headers=auth_headers)
    assert r.status_code == 404


def test_get_lead_consent_status(client: TestClient, auth_headers) -> None:
    r = client.get("/api/leads?page_size=1", headers=auth_headers)
    sample_id = r.json()["items"][0]["business_id"]
    r2 = client.get(f"/api/leads/{sample_id}", headers=auth_headers)
    d = r2.json()
    assert isinstance(d["consents"], list)
    for c in d["consents"]:
        assert c["channel"] in ("email", "phone", "sms", "marketing")
        assert c["status"] in ("granted", "revoked", "pending")
