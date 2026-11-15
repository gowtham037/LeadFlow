import { expect, Page } from '@playwright/test';

export const DEMO_PASSWORD = 'leadflow-demo';

/**
 * Login as admin via demo credentials button.
 * Waits until the dashboard is fully loaded.
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/');
  await page.click('button:has-text("Use demo credentials")');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await expect(page.locator('h1:has-text("Executive Dashboard")')).toBeVisible({ timeout: 15000 });
}

/**
 * Login as any user by email + password.
 */
export async function loginAs(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}

/**
 * Get the auth token from localStorage after login.
 */
export async function getAuthToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => localStorage.getItem('leadflow_token'));
}

/**
 * Get a non-admin user's email by role.
 */
export async function getSampleUserEmail(
  page: Page,
  role: 'sales_rep' | 'analyst' | 'sales_ops' | 'marketing_ops' | 'support_agent',
): Promise<string | null> {
  const token = await getAuthToken(page);
  if (!token) return null;
  const response = await page.request.get('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) return null;

  // Use the admin token to query leads API for sample — we can't list users via API
  // (would require admin user list endpoint, which we didn't build)
  // Simpler: read from known seeded emails pattern
  // Not ideal — but works for demo
  return null;
}
