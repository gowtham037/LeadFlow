"""
API tests — opportunities.

Covers:
  - List with filters/pagination/sort
  - Detail with stage history
  - Advance endpoint (valid + invalid transitions)
  - Close endpoint (won/lost)
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _get_an_open_opp(client: TestClient, headers: dict) -> dict:
    r = client.get("/api/opportunities?status=open&page_size=1", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    if not items:
        import pytest
        pytest.skip("No open opportunities to test")
    return items[0]


def test_list_opportunities_auth_required(client: TestClient) -> None:
    r = client.get("/api/opportunities")
    assert r.status_code == 401


def test_list_opportunities_basic(client: TestClient, auth_headers) -> None:
    r = client.get("/api/opportunities?page_size=5", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert len(d["items"]) <= 5
    assert d["total"] > 0


def test_list_opportunities_filter_status(client: TestClient, auth_headers) -> None:
    r = client.get("/api/opportunities?status=won&page_size=10", headers=auth_headers)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "won"


def test_list_opportunities_sort_by_amount(client: TestClient, auth_headers) -> None:
    r = client.get("/api/opportunities?sort_by=amount&order=desc&page_size=5", headers=auth_headers)
    assert r.status_code == 200
    amounts = [i["amount_usd"] for i in r.json()["items"]]
    assert amounts == sorted(amounts, reverse=True)


def test_opportunity_summary(client: TestClient, auth_headers) -> None:
    r = client.get("/api/opportunities/stats/summary", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["total_opportunities"] > 0
    assert "by_status" in d
    assert "won_revenue" in d


def test_get_opportunity_detail(client: TestClient, auth_headers) -> None:
    opp = _get_an_open_opp(client, auth_headers)
    r = client.get(f"/api/opportunities/{opp['business_id']}", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["business_id"] == opp["business_id"]
    assert "stage_history" in d
    assert isinstance(d["stage_history"], list)
    assert len(d["stage_history"]) >= 1  # at least the creation event


def test_get_opportunity_404(client: TestClient, auth_headers) -> None:
    r = client.get("/api/opportunities/OPP-2026-999999", headers=auth_headers)
    assert r.status_code == 404


def test_advance_stage_valid(client: TestClient, auth_headers) -> None:
    """Find a discovery-stage opp, advance to qualification."""
    r = client.get("/api/opportunities?stage=discovery&status=open&page_size=5", headers=auth_headers)
    items = r.json()["items"]
    if not items:
        import pytest
        pytest.skip("No discovery-stage opps to advance")

    target = items[0]
    resp = client.post(
        f"/api/opportunities/{target['business_id']}/advance",
        json={"to_stage": "qualification"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "qualification"


def test_advance_stage_invalid_skip_400(client: TestClient, auth_headers) -> None:
    """Try to skip from discovery directly to proposal — should 400."""
    r = client.get("/api/opportunities?stage=discovery&status=open&page_size=5", headers=auth_headers)
    items = r.json()["items"]
    if not items:
        import pytest
        pytest.skip("No discovery-stage opps")

    target = items[0]
    resp = client.post(
        f"/api/opportunities/{target['business_id']}/advance",
        json={"to_stage": "proposal"},  # skips qualification
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "skip" in resp.json()["detail"].lower() or "Cannot" in resp.json()["detail"]


def test_close_lost_requires_reason(client: TestClient, auth_headers) -> None:
    opp = _get_an_open_opp(client, auth_headers)
    resp = client.post(
        f"/api/opportunities/{opp['business_id']}/close",
        json={"status": "lost"},  # no lost_reason
        headers=auth_headers,
    )
    assert resp.status_code == 400
