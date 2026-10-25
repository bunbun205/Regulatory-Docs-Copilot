import { test, expect } from '@playwright/test';
import type { Route } from '@playwright/test';
import { capture, connected, setup } from './helpers.js';
import { askFixture, source } from './fixtures.js';

for (const width of [1280, 390, 360]) {
  test(`Ask answers, excerpts, controls and history fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/ask'); await connected(page);
    await page.getByText('Advanced', { exact: true }).click(); await page.getByRole('button', { name: 'Filters', exact: true }).click();
    await page.getByLabel('Agency', { exact: true }).fill('Synthetic test source'); await page.getByLabel('Start year').fill('2026'); await page.getByLabel('End year').fill('2020');
    await expect(page.getByRole('button', { name: 'Ask documents' })).toBeDisabled();
    await capture(page, `ask-filters-invalid-light-${width}`);
    await page.getByLabel('End year').fill('2026'); await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByLabel('Your question').fill(source); await page.getByLabel('Your question').press('Control+Enter');
    await expect(page.getByRole('button', { name: 'Citations checked', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Citations checked', exact: true }).click();
    await page.getByText('Details', { exact: true }).click(); await page.getByText('Session history (1/10)', { exact: true }).click();
    await capture(page, `ask-answer-history-light-${width}`);
    const chip = page.getByRole('button', { name: /Source 1: Instrument/ }); await chip.click();
    const drawer = page.getByRole('dialog', { name: 'Source excerpt' }); await expect(drawer.getByText('Synthetic test source', { exact: true })).toBeVisible();
    await expect(drawer.getByRole('heading', { name: 'Excerpt', exact: true })).toBeVisible();
    await capture(page, `ask-source-light-${width}`); await page.keyboard.press('Escape'); await expect(chip).toBeFocused();
    await page.route('**/api/v1/documents/*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'fixture_metadata_failure', message: 'Explicit browser fixture: metadata temporarily unavailable.' } }) }));
    await chip.click(); await expect(drawer.getByRole('alert')).toBeVisible(); await capture(page, `ask-source-metadata-error-light-${width}`); await page.keyboard.press('Escape');
    await page.getByRole('link', { name: /Open as search/ }).click(); await expect(page.getByLabel('Search your library')).toHaveValue(source);
    await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByRole('heading', { name: /Instrument checks/ })).toBeVisible();
    await capture(page, `search-results-light-${width}`);
    await page.getByLabel('Compare backends').check(); await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByText('1 of 1 shared', { exact: true })).toBeVisible();
    await capture(page, `search-compare-light-${width}`);
    // An explicit response fixture for a partial backend outage; the successful side is real.
    await page.route('**/api/v1/search', async route => route.request().postDataJSON().backend === 'qdrant' ? route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'fixture_outage', message: 'Explicit browser fixture: Qdrant outage.' } }) }) : route.continue());
    await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByRole('alert')).toBeVisible(); await expect(page.getByRole('heading', { name: /Instrument checks/ })).toBeVisible();
    await capture(page, `search-compare-partial-error-light-${width}`);
    await page.unroute('**/api/v1/search'); await page.getByLabel('Compare backends').uncheck();
    await page.getByRole('button', { name: 'Filters', exact: true }).click(); await page.getByLabel('Agency', { exact: true }).fill('No matching fixture agency'); await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByText('No passages found', { exact: true })).toBeVisible(); await capture(page, `search-empty-light-${width}`);
    let heldSearch: Route | undefined;
    await page.route('**/api/v1/search', route => { heldSearch = route; });
    await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByRole('button', { name: 'Stop waiting' })).toBeVisible(); await capture(page, `search-pending-light-${width}`);
    await page.getByRole('button', { name: 'Stop waiting' }).click(); await expect(page.getByText('Stopped waiting. The server may keep working.')).toBeVisible(); await capture(page, `search-stopped-light-${width}`); await heldSearch?.abort().catch(() => {});
  });
  test(`Ask pending, stopped, abstention, ungrounded and errors fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/ask'); await connected(page);
    let held: Route | undefined;
    await page.route('**/api/v1/ask', route => { held = route; }); await page.getByLabel('Your question').fill('Explicit pending response fixture'); await page.getByRole('button', { name: 'Ask documents' }).click();
    await expect(page.getByRole('button', { name: 'Stop waiting', exact: true })).toBeVisible(); await capture(page, `ask-pending-light-${width}`);
    await page.getByRole('button', { name: 'Stop waiting', exact: true }).click(); await expect(page.getByText('Stopped waiting. The server may keep working.')).toBeVisible(); await capture(page, `ask-stopped-light-${width}`);
    await held?.fulfill({ json: askFixture }).catch(() => {}); await page.unroute('**/api/v1/ask');
    await page.route('**/api/v1/ask', route => route.fulfill({ json: { ...askFixture, answer: 'Explicit browser abstention fixture: not enough evidence in the loaded documents.', insufficient_evidence: true, grounded: false, citations: [], top_score: 0.12 } }));
    await page.getByRole('button', { name: 'Ask documents' }).click(); await expect(page.getByText('Not enough evidence', { exact: true })).toBeVisible(); await capture(page, `ask-abstention-light-${width}`); await page.unroute('**/api/v1/ask');
    await page.route('**/api/v1/ask', route => route.fulfill({ json: { ...askFixture, answer: '<img src=x onerror=alert(1)> Explicit ungrounded fixture [99].', grounded: false, citations: [] } }));
    await page.getByRole('button', { name: 'Ask documents' }).click(); await expect(page.getByText('Sources need review', { exact: true })).toBeVisible(); await expect(page.locator('main img')).toHaveCount(0); await capture(page, `ask-ungrounded-light-${width}`); await page.unroute('**/api/v1/ask');
    await page.route('**/api/v1/ask', route => route.fulfill({ status: 429, headers: { 'Retry-After': '4' }, json: { error: { code: 'rate_limited', message: 'Explicit rate-limit fixture.', request_id: 'f2-429-fixture' } } }));
    await page.getByRole('button', { name: 'Ask documents' }).click(); await expect(page.getByRole('alert')).toContainText('Too many requests'); await capture(page, `ask-rate-limit-light-${width}`);
    await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeEnabled({ timeout: 6000 });
    await page.unroute('**/api/v1/ask'); await page.route('**/api/v1/ask', route => route.fulfill({ status: 502, json: { error: { code: 'fixture_timeout', message: 'Explicit model-timeout fixture.', request_id: 'f2-502-fixture' } } }));
    await page.getByRole('button', { name: 'Retry', exact: true }).click(); await expect(page.getByRole('alert')).toContainText('required service is unavailable'); await capture(page, `ask-error-light-${width}`);
  });
}
