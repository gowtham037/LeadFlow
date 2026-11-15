/**
 * E2E test — full user journey. 8 tests covering:
 *  1. Login (invalid → error)
 *  2. Login (valid → dashboard)
 *  3. Dashboard KPIs (uses getByText, not regex)
 *  4. Leads → filter → click → detail
 *  5. Opportunities pipeline
 *  6. Exceptions — 5 anomalies visible
 *  7. Admin → run validation → report renders
 *  8. Sign out returns to login
 */
import { test, expect } from '@playwright/test';

const DEMO_EMAIL = 'laura.boone.46@leadflow-demo.io';
const DEMO_PASSWORD = 'leadflow-demo';

async function loginAsAdmin(page: any) {
  await page.goto('/');
  await page.click('button:has-text("Use demo credentials")');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  // Wait for dashboard to load data
  await expect(page.locator('h1:has-text("Executive Dashboard")')).toBeVisible({ timeout: 15000 });
}

test.describe('LeadFlow — full user journey', () => {
  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);

    await page.fill('input[type="email"]', 'nobody@example.com');
    await page.fill('input[type="password"]', 'wrongpw');
    await page.click('button[type="submit"]');

    await expect(page.locator('text=/Invalid credentials/i')).toBeVisible({ timeout: 8000 });
  });

  test('login with valid credentials lands on dashboard', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.locator('h1:has-text("Executive Dashboard")')).toBeVisible();
  });

  test('dashboard shows key KPIs', async ({ page }) => {
    await loginAsAdmin(page);

    // KPI cards — use getByText with exact: true and .first() to handle any duplicate text
    await expect(page.getByText('Total Leads', { exact: true }).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Conversion Rate', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Revenue Won', { exact: true }).first()).toBeVisible();

    // Score strategy table header (unique text)
    await expect(page.getByText('Scoring Strategy Performance', { exact: true })).toBeVisible({ timeout: 10000 });

    // Funnel + score distribution chart titles (unique)
    await expect(page.getByText('Conversion Funnel', { exact: true })).toBeVisible();
    await expect(page.getByText('Score Distribution', { exact: true })).toBeVisible();
  });

  test('leads page → filter HOT → click lead → detail page', async ({ page }) => {
    await loginAsAdmin(page);

    await page.click('a[href="/leads"]');
    await expect(page).toHaveURL(/\/leads/);
    await expect(page.locator('h1:has-text("Lead Management")')).toBeVisible();

    // Filter by HOT tier (2nd select on page = category filter)
    const categorySelect = page.locator('select').nth(1);
    await categorySelect.selectOption('hot');
    await page.waitForTimeout(1000);

    const firstLink = page.locator('table tbody tr a').first();
    await expect(firstLink).toBeVisible({ timeout: 10000 });
    const href = await firstLink.getAttribute('href');
    expect(href).toMatch(/\/leads\/LEAD-2026-\d+/);

    await firstLink.click();
    await expect(page).toHaveURL(/\/leads\/LEAD-2026-/);

    await expect(page.getByText('Score Explanation', { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Fit', { exact: true })).toBeVisible();
    await expect(page.getByText('Intent', { exact: true })).toBeVisible();
    await expect(page.getByText('Consent Status (per-channel)', { exact: true })).toBeVisible();
  });

  test('opportunities page loads pipeline', async ({ page }) => {
    await loginAsAdmin(page);

    await page.click('a[href="/opportunities"]');
    await expect(page).toHaveURL(/\/opportunities/);
    await expect(page.locator('h1:has-text("Opportunity Pipeline")')).toBeVisible();
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 });
  });

  test('exceptions page shows the 5 anomalies', async ({ page }) => {
    await loginAsAdmin(page);

    await page.click('a[href="/exceptions"]');
    await expect(page).toHaveURL(/\/exceptions/);
    await expect(page.locator('h1:has-text("Exception Center")')).toBeVisible();

    // All 5 anomaly types visible
    await expect(page.locator('text=/optout_contacted/')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/post_conversion_scoring/')).toBeVisible();
    await expect(page.locator('text=/territory_mismatch/')).toBeVisible();
    await expect(page.locator('text=/duplicate_opportunity/')).toBeVisible();
    await expect(page.locator('text=/stage_gap/')).toBeVisible();
  });

  test('admin → run validation → report shows', async ({ page }) => {
    await loginAsAdmin(page);

    await page.click('a[href="/admin"]');
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.locator('h1:has-text("Administration")')).toBeVisible();

    // Wait for all 5 action cards to render
    await expect(page.getByText('Run Data Validation', { exact: true })).toBeVisible({ timeout: 10000 });

    // Find the card that contains both "Run Data Validation" heading AND a Run button.
    // Approach: locate the button by filtering its ancestor div.
    const runButton = page
      .locator('div')
      .filter({ has: page.getByText('Run Data Validation', { exact: true }) })
      .filter({ has: page.locator('button:has-text("Run")') })
      .locator('button:has-text("Run")')
      .last();  // innermost match

    await runButton.click();

    // Validation report appears after ~3-8s (18 checks against live DB)
    await expect(page.getByText('Validation Report', { exact: true })).toBeVisible({ timeout: 30000 });
    // Sanity — some "passed" text present
    await expect(page.locator('text=/passed/').first()).toBeVisible();
  });

  test('sign out returns to login', async ({ page }) => {
    await loginAsAdmin(page);

    await page.click('button:has-text("Sign out")');
    await expect(page).toHaveURL(/\/login/, { timeout: 8000 });
  });
});
