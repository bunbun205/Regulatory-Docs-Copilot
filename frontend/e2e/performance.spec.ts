import { test, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { capture, connected, evidenceDirectory, setup, writer } from './helpers.js';
import type { components } from '../src/types/api.js';

for (const width of [1280, 390, 360]) test(`large isolated corpus and 1000-finding report ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 }); await setup(page);
  let active = 0; let peak = 0; let detailRequests = 0;
  const requests = new Set(); const measurements: Record<string, number> = {};
  page.on('request', request => { if (/\/api\/v1\/documents\/[^/?]+$/.test(request.url())) { requests.add(request); active++; detailRequests++; peak = Math.max(peak, active); } });
  const done = (request: unknown) => { if (requests.delete(request)) active--; };
  page.on('requestfinished', done); page.on('requestfailed', done);
  const countsReady = async () => { await expect(page.getByRole('table')).toBeVisible(); await expect(page.getByLabel('Loading chunk count')).toHaveCount(0); };
  let began = Date.now(); await page.goto('/documents'); await connected(page); await countsReady(); measurements.first_page_ms = Date.now() - began;
  await expect(page.getByText('Loaded 1–10 of 5001 documents', { exact: true })).toBeVisible();
  began = Date.now(); await page.getByLabel('Rows per page').selectOption('50'); await expect(page.getByText('Loaded 1–50 of 5001 documents', { exact: true })).toBeVisible(); await countsReady(); measurements.fifty_rows_ms = Date.now() - began;
  const beforeNext = detailRequests; began = Date.now(); await page.getByRole('button', { name: 'Next page', exact: true }).click(); await expect(page.getByText('Loaded 51–100 of 5001 documents', { exact: true })).toBeVisible(); await countsReady(); measurements.next_page_ms = Date.now() - began; expect(detailRequests - beforeNext).toBe(50);
  const beforeBack = detailRequests; began = Date.now(); await page.getByRole('button', { name: 'Previous page', exact: true }).click(); await expect(page.getByText('Loaded 1–50 of 5001 documents', { exact: true })).toBeVisible(); await countsReady(); measurements.cached_page_ms = Date.now() - began; const cachedBackRequests = detailRequests - beforeBack; expect(cachedBackRequests).toBe(0); expect(peak).toBeLessThanOrEqual(3);
  await page.getByText('Filter the library', { exact: true }).click(); await page.getByLabel('Agency', { exact: true }).fill('Performance target'); began = Date.now(); await page.getByRole('button', { name: 'Apply filters', exact: true }).click(); await expect(page.getByText('Loaded 1–50 of 50 documents', { exact: true })).toBeVisible(); await countsReady(); measurements.filtered_page_ms = Date.now() - began;
  await capture(page, `performance-library-${width}`);
  for (const backend of ['pgvector', 'qdrant']) {
    began = Date.now(); const found = await page.request.post('/api/v1/search', { headers: { 'X-API-Key': writer }, data: { query: 'Synthetic performance document 400, chunk 0.', backend, top_k: 5, filters: { source_agency: 'Performance target' } } });
    expect(found.ok()).toBe(true); expect((await found.json()).results).toHaveLength(5); measurements[`${backend}_filtered_search_ms`] = Date.now() - began;
  }
  began = Date.now(); await page.goto('/gap-check'); await expect(page.getByText('5001 documents match these filters.', { exact: true })).toBeVisible(); measurements.gap_scope_ms = Date.now() - began;

  const fixtureId = '10000000-0000-4000-8000-000000000006'; const response = await page.request.get(`/api/v1/gapcheck/${fixtureId}`, { headers: { 'X-API-Key': writer } }); const job = await response.json() as components['schemas']['GapCheckJobResponse']; const report = job.report!;
  const findings = Array.from({ length: 1000 }, (_, i) => ({ ...report.findings[2], finding_id: `GAP-${String(i + 1).padStart(4, '0')}`, rationale: `Synthetic large-report finding ${i + 1}. ${'Review the quoted evidence and limitations. '.repeat(12)}` }));
  await page.route(`**/api/v1/gapcheck/${fixtureId}`, route => route.fulfill({ json: { ...job, report: { ...report, findings, counts_by_verdict: { conflict: 1000 }, counts_by_severity: { high: 1000, medium: 0, low: 0 } } } }));
  began = Date.now(); await page.goto(`/gap-check/${fixtureId}`); await expect(page.getByRole('article')).toHaveCount(1000); measurements.report_render_ms = Date.now() - began; expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  began = Date.now(); await page.getByLabel('Search findings', { exact: true }).fill('GAP-0999'); await expect(page.getByRole('article')).toHaveCount(1); measurements.report_filter_ms = Date.now() - began; await capture(page, `performance-report-filtered-${width}`);
  began = Date.now(); await page.evaluate(() => window.dispatchEvent(new Event('beforeprint'))); await expect(page.getByText('Compare evidence for GAP-0999', { exact: true }).locator('..')).toHaveAttribute('open'); measurements.selected_print_prepare_ms = Date.now() - began; await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
  const cdp = await page.context().newCDPSession(page); await cdp.send('Performance.enable'); const metrics = await cdp.send('Performance.getMetrics'); await cdp.detach();
  measurements.js_heap_used_bytes = metrics.metrics.find(metric => metric.name === 'JSHeapUsedSize')?.value ?? 0;
  await mkdir(evidenceDirectory, { recursive: true }); await writeFile(resolve(evidenceDirectory, `performance-${width}.json`), JSON.stringify({ description: '5000 synthetic documents/10000 chunks added to one seeded document/chunk in isolated Postgres and Qdrant; 1000-finding browser response fixture. Timings are observations, not quality scores or production capacity guarantees.', width, corpus_documents: 5001, corpus_chunks: 10001, measurements, peak_detail_requests: peak, detail_requests: detailRequests, cached_back_navigation_requests: cachedBackRequests, horizontal_page_overflow: false }, null, 2) + '\n');
});
