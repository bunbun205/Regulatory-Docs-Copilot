import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';

const directory = resolve('../docs/screenshots/f1');
// Fixed credentials exist only in the isolated e2e entrypoint, never in the main database.
const writer = 'frontend-e2e-write';
const reader = 'frontend-e2e-read';
const job = '10000000-0000-4000-8000-000000000003';

test('generated API types match the running committed-backend schema', () => {
  execFileSync(process.execPath, ['scripts/check-types.mjs'], { stdio: 'pipe' });
});

async function setup(page: Page, key = writer, theme = 'light') {
  await page.addInitScript(({ key, theme }) => {
    sessionStorage.setItem('labdocs_api_key', key);
    if (!localStorage.getItem('docs_copilot_preferences')) localStorage.setItem('docs_copilot_preferences', JSON.stringify({ baseUrl: '/api', backend: 'pgvector', topK: 2, theme }));
  }, { key, theme });
}
async function capture(page: Page, name: string) {
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: resolve(directory, `${name}.png`), fullPage: true, animations: 'disabled' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${name}: horizontal page overflow`).toBe(true);
}
async function connected(page: Page) { await expect(page.getByRole('link', { name: /Settings: API online, frontend-review/ })).toBeVisible(); }

for (const width of [1280, 390, 360]) {
  test(`every route fits ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await setup(page);
    const errors: string[] = [];
    const requests: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push(request.url()));
    const routes = [
      ['/ask', 'Ask your documents', 'ask'], ['/search', 'Search library', 'search'],
      ['/agent', 'Research agent', 'agent'], ['/gap-check', 'Gap check', 'gap-check'],
      [`/gap-check/${job}`, 'Gap check', 'gap-job'], ['/documents', 'Documents', 'documents'],
      ['/settings', 'Settings', 'settings-valid'],
    ];
    for (const [path, title, name] of routes) {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: title, exact: true, level: 1 })).toBeVisible();
      await connected(page);
      if (name === 'ask') await expect(page.getByLabel('Your question')).toBeVisible();
      if (name === 'search') await expect(page.getByLabel('Search your library')).toBeVisible();
      if (name === 'agent') await expect(page.getByLabel('Research question')).toBeVisible();
      if (name === 'gap-check') await expect(page.getByLabel('SOP text')).toBeVisible();
      if (name === 'gap-job') await expect(page.getByRole('heading', { name: 'Findings report' })).toBeVisible();
      if (name === 'documents') await expect(page.getByRole('table')).toBeVisible();
      if (name === 'settings-valid') await expect(page.getByText('Connection verified', { exact: true })).toBeVisible();
      await capture(page, `${name}-light-${width}`);
    }
    expect(errors).toEqual([]);
    expect(requests.every(url => url.startsWith('http://127.0.0.1:3100/'))).toBe(true);
    expect(requests.some(url => url.includes(writer) || url.includes(reader))).toBe(false);
    expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(writer);
  });
}

for (const width of [1280, 390]) {
  test(`Settings invalid key and shared error at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page);
    await page.goto('/settings'); await connected(page);
    await page.getByLabel('API key', { exact: true }).fill('invalid-browser-fixture');
    await page.getByRole('button', { name: 'Validate key', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Your API key is missing or invalid');
    await capture(page, `settings-invalid-light-${width}`);
    await page.getByLabel('API key', { exact: true }).fill(writer);
    await page.getByRole('button', { name: 'Validate key', exact: true }).click();
    await expect(page.getByText('Connection verified', { exact: true })).toBeVisible();
    await page.route('**/api/v1/search', route => route.fulfill({ status: 502, contentType: 'application/json', headers: { 'X-Request-ID': 'f1-error-fixture' }, body: JSON.stringify({ error: { code: 'llm_unavailable', message: 'The language model is unavailable.', request_id: 'f1-error-fixture' } }) }));
    await page.goto('/search'); await connected(page);
    await page.getByLabel('Search your library').fill('Instrument checks');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('required service is unavailable');
    await capture(page, `shared-error-light-${width}`);
    await page.getByText('Details', { exact: true }).click();
    await expect(page.locator('pre')).toContainText('f1-error-fixture');
  });
  test(`read-only Settings and upload scope at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page, reader);
    await page.goto('/settings'); await expect(page.getByText('Read-only key', { exact: true })).toBeVisible();
    await capture(page, `settings-read-only-light-${width}`);
    await page.goto('/documents'); await expect(page.getByText('This key is read only.', { exact: false })).toBeVisible();
    await expect(page.getByLabel('File', { exact: true })).toHaveCount(0);
  });
  test(`dark shell and Settings at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page, writer, 'dark');
    await page.goto('/ask'); await connected(page); await expect(page.getByLabel('Your question')).toBeVisible(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await capture(page, `ask-dark-${width}`);
    await page.goto('/settings'); await connected(page); await expect(page.getByText('Connection verified', { exact: true })).toBeVisible();
    await capture(page, `settings-valid-dark-${width}`);
  });
}

test('mobile navigation keyboard, default route and theme persistence', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 900 }); await setup(page);
  await page.goto('/'); await expect(page).toHaveURL(/\/ask$/); await connected(page);
  const opener = page.getByRole('button', { name: 'Open navigation' });
  await opener.click(); await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Shift+Tab'); await expect(page.getByRole('dialog').getByRole('link', { name: 'Settings' })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(opener).toBeFocused();
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  // Reload without the setup script resetting preferences.
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('docs_copilot_preferences') || '{}').theme)).toBe('dark');
  await page.reload(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});
