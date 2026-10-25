import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const directory = resolve(`../docs/screenshots/${process.env.FRONTEND_SCREENSHOT_MILESTONE || 'f5'}`);
// Fixed credentials exist only in the isolated e2e entrypoint, never in the main database.
export const writer = 'frontend-e2e-write';
export const reader = 'frontend-e2e-read';
export const job = '10000000-0000-4000-8000-000000000003';

export async function setup(page: Page, key = writer, theme = 'light') {
  await page.addInitScript(({ key, theme }) => {
    sessionStorage.setItem('labdocs_api_key', key);
    if (!localStorage.getItem('docs_copilot_preferences')) localStorage.setItem('docs_copilot_preferences', JSON.stringify({ baseUrl: '/api', backend: 'pgvector', topK: 2, theme }));
  }, { key, theme });
}
export async function capture(page: Page, name: string) {
  await mkdir(directory, { recursive: true });
  // Reset scrolling before full-page capture so sticky/fixed chrome is at its real top position.
  await page.evaluate(() => window.scrollTo(0, 0));
  const overlay = await page.getByRole('dialog').isVisible();
  await page.screenshot({ path: resolve(directory, `${name}.png`), fullPage: !overlay, animations: 'disabled' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${name}: horizontal page overflow`).toBe(true);
}
export async function connected(page: Page) { await expect(page.getByRole('link', { name: /Settings: API online, frontend-review/ })).toBeVisible(); }

export const evidenceDirectory = resolve(`../docs/verification/frontend-${process.env.FRONTEND_SCREENSHOT_MILESTONE || 'f5'}`);
