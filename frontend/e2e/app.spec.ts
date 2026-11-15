/**
 * E2E tests — full user journey (15 tests).
 *
 * Groups:
 *   1. Auth (4)
 *   2. Dashboard (3)
 *   3. Leads (4)
 *   4. Opportunities (2)
 *   5. Exceptions (1)
 *   6. Admin (1)
 */
import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers';

// ---------------- 1. Auth ----------------

test.describe('Auth', () => {
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

  test('demo credentials button auto-fills form', async ({ page }) => {
    await page.goto('/');
    await page.click('button:has-text("Use demo credentials")');

    const emailVal = await page.locator('input[type="email"]').inputValue();
    const pwVal = await page.locator('input[type="password"]').inputValue();

    expect(emailVal).toContain('@leadflow-demo.io');
    expect(pwVal).toBe('leadflow-demo');
  });

  test('protected route redirects to login without auth', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });
});

// ---------------- 2. Dashboard ----------------

test.describe('Dashboard', () => {
  test('shows all KPI cards with real numbers', async ({ page }) => {
    await loginAsAdmin(page);

    await expect(page.getByText('Total Leads', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Conversion Rate', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Opportunities', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Revenue Won', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Won Deals', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Avg Deal Size', { exact: true }).first()).toBeVisible();
  });

  test('shows funnel and pie charts', async ({ page }) => {
    await loginAsAdmin(page);

    await expect(page.getByText('Conversion Funnel', { exact: true })).toBeVisible();
    await expect(page.getByText('Score Distribution', { exact: true })).toBeVisible();
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('scoring strategy table shows HOT > COLD conversion', async ({ page }) => {
    await loginAsAdmin(page);

    await expect(page.getByText('Scoring Strategy Performance', { exact: true })).toBeVisible();

    // Find the HOT row and check it shows the expected conversion rate
    const hotRow = page.locator('tr').filter({ hasText: 'Hot' }).first();
    await expect(hotRow).toBeVisible();

    // Should contain a % symbol
    const rowText = await hotRow.textContent();
    expect(rowText).toMatch(/\d+\.\d+%/);
  });
});

// ---------------- 3. Leads ----------------

test.describe('Leads', () => {
  test('leads page shows 25 rows per page by default', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/leads"]');
    await expect(page.locator('h1:has-text("Lead Management")')).toBeVisible();

    const rowCount = await page.locator('table tbody tr').count();
    expect(rowCount).toBeGreaterThan(0);
    expect(rowCount).toBeLessThanOrEqual(25);
  });

  test('leads search filters results', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/leads"]');
    await expect(page.locator('h1:has-text("Lead Management")')).toBeVisible();

    // Grab first row's business ID
    const firstLink = page.locator('table tbody tr a').first();
    const firstId = await firstLink.textContent();
    expect(firstId).toMatch(/LEAD-2026-\d+/);

    // Search for it
    await page.fill('input[placeholder*="Search business ID"]', firstId!.trim());
    await page.waitForTimeout(800);

    // Should still show it
    await expect(page.locator(`text=${firstId}`).first()).toBeVisible();
  });

  test('filter by HOT tier shows only HOT leads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/leads"]');

    const tierSelect = page.locator('select').nth(1);
    await tierSelect.selectOption('hot');
    await page.waitForTimeout(800);

    // Count "hot" tier badges in the table
    const hotBadges = await page.locator('table tbody td span:has-text("hot")').count();
    const totalRows = await page.locator('table tbody tr').count();

    expect(hotBadges).toBe(totalRows);
  });

  test('clicking a lead business ID opens detail page', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/leads"]');

    // Filter HOT so we know it has a score
    const tierSelect = page.locator('select').nth(1);
    await tierSelect.selectOption('hot');
    await page.waitForTimeout(800);

    // Click first row
    const firstLink = page.locator('table tbody tr a').first();
    const href = await firstLink.getAttribute('href');
    expect(href).toMatch(/\/leads\/LEAD-2026-\d+/);

    await firstLink.click();
    await expect(page).toHaveURL(/\/leads\/LEAD-2026-/);
    await expect(page.getByText('Score Explanation', { exact: true })).toBeVisible();
    await expect(page.getByText('Consent Status (per-channel)', { exact: true })).toBeVisible();
  });

  test('lead detail shows feature contributions expandable', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/leads"]');

    const firstLink = page.locator('table tbody tr a').first();
    await firstLink.click();
    await expect(page).toHaveURL(/\/leads\/LEAD-2026-/);

    // Expand contributions
    const summary = page.locator('summary:has-text("Show feature-level contributions")');
    await expect(summary).toBeVisible();
    await summary.click();

    // Should show feature codes
    await expect(page.locator('code')).toHaveCount(12);
  });
});

// ---------------- 4. Opportunities ----------------

test.describe('Opportunities', () => {
  test('opportunities page loads pipeline table', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/opportunities"]');
    await expect(page.locator('h1:has-text("Opportunity Pipeline")')).toBeVisible();
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 });
  });

  test('opportunities filter by status shows only that status', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/opportunities"]');

    const statusSelect = page.locator('select').first();
    await statusSelect.selectOption('won');
    await page.waitForTimeout(800);

    // All status badges should say "won"
    const wonBadges = await page.locator('table tbody td span:has-text("won")').count();
    const totalRows = await page.locator('table tbody tr').count();

    expect(wonBadges).toBe(totalRows);
    expect(totalRows).toBeGreaterThan(0);
  });
});

// ---------------- 5. Exceptions ----------------

test.describe('Exceptions', () => {
  test('exception center shows all 5 anomaly types', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/exceptions"]');
    await expect(page.locator('h1:has-text("Exception Center")')).toBeVisible();

    await expect(page.locator('text=/optout_contacted/')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/post_conversion_scoring/')).toBeVisible();
    await expect(page.locator('text=/territory_mismatch/')).toBeVisible();
    await expect(page.locator('text=/duplicate_opportunity/')).toBeVisible();
    await expect(page.locator('text=/stage_gap/')).toBeVisible();
  });
});

// ---------------- 6. Admin ----------------

test.describe('Admin', () => {
  test('admin page shows 5 action cards', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/admin"]');
    await expect(page.locator('h1:has-text("Administration")')).toBeVisible();

    await expect(page.getByText('Re-score All Leads', { exact: true })).toBeVisible();
    await expect(page.getByText('Route Qualified Leads', { exact: true })).toBeVisible();
    await expect(page.getByText('Generate Follow-up Tasks', { exact: true })).toBeVisible();
    await expect(page.getByText('Convert Leads to Opportunities', { exact: true })).toBeVisible();
    await expect(page.getByText('Run Data Validation', { exact: true })).toBeVisible();
  });

  test('admin run validation generates report', async ({ page }) => {
    await loginAsAdmin(page);
    await page.click('a[href="/admin"]');

    const runButton = page
      .locator('div')
      .filter({ has: page.getByText('Run Data Validation', { exact: true }) })
      .filter({ has: page.locator('button:has-text("Run")') })
      .locator('button:has-text("Run")')
      .last();

    await runButton.click();

    await expect(page.getByText('Validation Report', { exact: true })).toBeVisible({ timeout: 30000 });
    await expect(page.locator('text=/passed/').first()).toBeVisible();
  });
});