import { test, expect } from '@playwright/test';
import type { Route } from '@playwright/test';
import type { components } from '../src/types/api.js';
import { capture, connected, setup } from './helpers.js';
import { askFixture, source } from './fixtures.js';

const partial: components['schemas']['AgentResponse'] = { query: 'Explicit partial browser fixture', backend: 'pgvector', answer: 'This is an incomplete fixture answer. [1]', citations: askFixture.citations, grounded: false, grounding_reason: 'partial', partial: true, partial_reason: 'step_limit', step_count: 1, trace: [{ step: 1, tool: 'search_documents', arguments: { query: '<script>untrusted()</script>', top_k: 2 }, result_summary: 'Explicit browser fixture: one chunk returned; output truncated', latency_ms: 24, error: 'Explicit browser fixture: tool failure' }], usage: askFixture.usage, latency_ms: 150 };
for (const width of [1280, 390, 360]) {
  test(`Agent real tools, excerpts, partial and empty states fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/agent'); await connected(page);
    await page.getByLabel('Research question').fill(source); await page.getByRole('button', { name: 'Run agent', exact: true }).click();
    await expect(page.getByText('Citations checked', { exact: true })).toBeVisible();
    await page.getByText('View tool steps (2)', { exact: true }).click(); await page.getByText('Arguments for step 2', { exact: true }).click(); await page.getByText('Details', { exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Query document metadata', exact: true })).toBeVisible(); await expect(page.getByRole('heading', { name: 'Search documents', exact: true })).toBeVisible();
    await capture(page, `agent-trace-light-${width}`);
    const chip = page.getByRole('button', { name: /^Source 1:/ }); await chip.click(); await expect(page.getByRole('dialog').getByText('Synthetic test source', { exact: true })).toBeVisible(); await capture(page, `agent-source-light-${width}`); await page.keyboard.press('Escape'); await expect(chip).toBeFocused();
    await page.route('**/api/v1/agent/run', route => route.fulfill({ json: partial })); await page.getByRole('button', { name: 'Run agent', exact: true }).click(); await expect(page.getByText('This run is incomplete', { exact: true })).toBeVisible(); await expect(page.getByText('Sources need review', { exact: true })).toBeVisible();
    await page.getByText('View tool steps (1)', { exact: true }).click(); await page.getByText('Arguments for step 1', { exact: true }).click(); await expect(page.locator('main script, main img')).toHaveCount(0); await capture(page, `agent-partial-error-truncated-light-${width}`); await page.unroute('**/api/v1/agent/run');
    await page.route('**/api/v1/agent/run', route => route.fulfill({ json: { ...partial, partial_reason: 'timeout', answer: '', citations: [], trace: [], step_count: 0 } })); await page.getByRole('button', { name: 'Run agent', exact: true }).click(); await expect(page.getByText('No tool steps were completed.', { exact: true })).toBeVisible(); await capture(page, `agent-timeout-empty-light-${width}`);
  });
  test(`Agent pending, Stop waiting and shared failure fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/agent'); await connected(page);
    let held: Route | undefined; await page.route('**/api/v1/agent/run', route => { held = route; });
    await page.getByLabel('Research question').fill('Explicit pending Agent fixture'); await page.getByRole('button', { name: 'Run agent', exact: true }).click(); await expect(page.getByRole('button', { name: 'Stop waiting', exact: true })).toBeVisible(); await capture(page, `agent-pending-light-${width}`);
    await page.getByRole('button', { name: 'Stop waiting', exact: true }).click(); await expect(page.getByText('Stopped waiting. The server may keep working.')).toBeVisible(); await capture(page, `agent-stopped-light-${width}`); await held?.abort().catch(() => {}); await page.unroute('**/api/v1/agent/run');
    await page.route('**/api/v1/agent/run', route => route.fulfill({ status: 502, json: { error: { code: 'llm_unavailable', message: 'Explicit Agent failure fixture', request_id: 'f3-agent-error' } } })); await page.getByRole('button', { name: 'Run agent', exact: true }).click(); await expect(page.getByRole('alert')).toBeVisible(); await capture(page, `agent-error-light-${width}`);
  });
}
