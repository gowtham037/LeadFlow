/**
 * E2E tests — API-level RBAC + validation.
 *
 * Runs API requests via Playwright's `request` fixture — same auth,
 * different layer. Proves backend enforces permissions regardless of UI.
 */
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://localhost:8002';

async function login(email = 'laura.boone.46@leadflow-demo.io', password = 'leadflow-demo'): Promise<string> {
  const resp = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  expect(resp.ok).toBeTruthy();
  const json = await resp.json();
  return json.access_token;
}

test.describe('API RBAC + validation', () => {
  test('unauthenticated request is rejected with 401', async ({ request }) => {
    const resp = await request.get(`${API}/api/leads`);
    expect(resp.status()).toBe(401);
  });

  test('admin can access admin endpoints', async ({ request }) => {
    const token = await login();
    const resp = await request.get(`${API}/api/admin/pipeline-stats`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.leads).toBeGreaterThan(0);
  });

  test('non-existent lead returns 404', async ({ request }) => {
    const token = await login();
    const resp = await request.get(`${API}/api/leads/LEAD-2026-999999`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(resp.status()).toBe(404);
  });

  test('advancing opp with skipped stage returns 400', async ({ request }) => {
    const token = await login();

    // Find a discovery-stage opp
    const listResp = await request.get(`${API}/api/opportunities?stage=discovery&status=open&page_size=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const opps = await listResp.json();
    test.skip(!opps.items?.length, 'No discovery-stage opps to test');

    const target = opps.items[0];

    // Try to skip directly to proposal (should be rejected)
    const resp = await request.post(`${API}/api/opportunities/${target.business_id}/advance`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { to_stage: 'proposal' },
    });

    expect(resp.status()).toBe(400);
    const err = await resp.json();
    expect(err.detail.toLowerCase()).toContain('skip');
  });

  test('closing opp as lost without reason returns 400', async ({ request }) => {
    const token = await login();

    const listResp = await request.get(`${API}/api/opportunities?status=open&page_size=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const opps = await listResp.json();
    test.skip(!opps.items?.length, 'No open opps to test');

    const resp = await request.post(`${API}/api/opportunities/${opps.items[0].business_id}/close`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { status: 'lost' },
    });

    expect(resp.status()).toBe(400);
  });

  test('analytics dashboard returns expected KPI shape', async ({ request }) => {
    const token = await login();
    const resp = await request.get(`${API}/api/analytics/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(resp.ok()).toBeTruthy();

    const data = await resp.json();
    expect(data).toHaveProperty('leads');
    expect(data).toHaveProperty('opportunities');
    expect(data).toHaveProperty('funnel');
    expect(data).toHaveProperty('score_categories');
    expect(data.leads.total_leads).toBeGreaterThan(0);
  });

  test('scoring engine proves HOT > COLD conversion', async ({ request }) => {
    const token = await login();
    const resp = await request.get(`${API}/api/analytics/score-category-performance`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(resp.ok()).toBeTruthy();

    const cats = await resp.json();
    const hot = cats.find((c: any) => c.category === 'hot');
    const cold = cats.find((c: any) => c.category === 'cold');

    expect(hot).toBeDefined();
    expect(cold).toBeDefined();
    expect(hot.conversion_rate).toBeGreaterThan(cold.conversion_rate);
  });

  test('pagination returns disjoint pages', async ({ request }) => {
    const token = await login();

    const p1 = await request.get(`${API}/api/leads?page=1&page_size=5`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const p2 = await request.get(`${API}/api/leads?page=2&page_size=5`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    const ids1 = new Set((await p1.json()).items.map((i: any) => i.business_id));
    const ids2 = new Set((await p2.json()).items.map((i: any) => i.business_id));

    for (const id of ids2) {
      expect(ids1.has(id)).toBeFalsy();
    }
  });
});
