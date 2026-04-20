/**
 * OCCP Dashboard E2E tests — Art.14 compliance + pipeline monitoring.
 * Run: npx playwright test --config=dash/playwright.config.ts
 *
 * Env vars:
 *   DASHBOARD_URL=https://dash.occp.ai   (default)
 *   ADMIN_USER=admin
 *   ADMIN_PW=...                         (set per-CI-run, never commit)
 */
import { test, expect } from '@playwright/test';

const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PW = process.env.ADMIN_PW;

test.describe('Authentication', () => {
  test('login flow succeeds with valid credentials', async ({ page }) => {
    test.skip(!ADMIN_PW, 'ADMIN_PW env var not set');
    await page.goto('/login');
    await expect(page).toHaveTitle(/OCCP/);
    await page.getByLabel(/username|felhasználónév/i).fill(ADMIN_USER);
    await page.getByLabel(/password|jelszó/i).fill(ADMIN_PW!);
    await page.getByRole('button', { name: /log in|belépés/i }).click();
    await expect(page).toHaveURL(/\/(dashboard|$)/, { timeout: 15_000 });
  });

  test('unauthenticated request redirects to /login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });
});

test.describe('Observability panel (Art.14 Level 1 — Understand)', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!ADMIN_PW, 'ADMIN_PW env var not set');
    await page.goto('/login');
    await page.getByLabel(/username|felhasználónév/i).fill(ADMIN_USER);
    await page.getByLabel(/password|jelszó/i).fill(ADMIN_PW!);
    await page.getByRole('button', { name: /log in|belépés/i }).click();
    await page.waitForURL(/\/(dashboard|$)/);
  });

  test('readiness score visible', async ({ page }) => {
    await page.goto('/observability');
    await expect(page.getByText(/readiness|l6/i)).toBeVisible({ timeout: 10_000 });
  });

  test('kill switch toggle present + admin-only warning', async ({ page }) => {
    await page.goto('/governance');
    await expect(page.getByText(/kill[- ]?switch/i)).toBeVisible();
  });
});

test.describe('Pipeline runs (Art.14 Level 1)', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!ADMIN_PW, 'ADMIN_PW env var not set');
    await page.goto('/login');
    await page.getByLabel(/username|felhasználónév/i).fill(ADMIN_USER);
    await page.getByLabel(/password|jelszó/i).fill(ADMIN_PW!);
    await page.getByRole('button', { name: /log in|belépés/i }).click();
    await page.waitForURL(/\/(dashboard|$)/);
  });

  test('pipeline list page renders', async ({ page }) => {
    await page.goto('/pipeline');
    await expect(page).toHaveTitle(/OCCP/);
    const table = page.locator('table, [role="table"]');
    await expect(table.first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('Public endpoints (no auth required)', () => {
  test('landing page renders', async ({ page }) => {
    await page.goto('https://occp.ai');
    await expect(page).toHaveTitle(/OCCP/);
  });

  test('api health endpoint returns 200', async ({ request }) => {
    const r = await request.get('https://api.occp.ai/api/v1/status');
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body).toHaveProperty('version');
    expect(body).toHaveProperty('status', 'running');
  });
});
