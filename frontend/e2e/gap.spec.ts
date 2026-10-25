import { test, expect } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { components } from '../src/types/api.js';
import { capture, connected, setup, writer } from './helpers.js';
import { source } from './fixtures.js';

const evidence = resolve('../docs/verification/frontend-f4');
const reportJob = '10000000-0000-4000-8000-000000000006';
const fixtureJob = '10000000-0000-4000-8000-000000000007';
type Job = components['schemas']['GapCheckJobResponse'];

for (const width of [1280, 390, 360]) {
  test(`Gap real paste, reload, report, file upload and cancellation fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/gap-check'); await connected(page);
    await expect(page.getByText('1 document matches these filters.', { exact: true })).toBeVisible();
    const sop = `# Browser walkthrough ${width}\n\n${source}\n\nThis clause describes a synthetic astronomy workflow for ${width}.`;
    await page.getByLabel('SOP text', { exact: true }).fill(sop); await page.getByText('Documents in scope', { exact: true }).click(); await capture(page, `gap-input-light-${width}`);
    const began = Date.now(); await page.getByRole('button', { name: 'Run gap check', exact: true }).click(); await expect(page).toHaveURL(/\/gap-check\/[0-9a-f-]+$/);
    const runUrl = page.url(); await expect(page.getByText('Review in progress', { exact: true })).toBeVisible(); await capture(page, `gap-progress-light-${width}`);
    await page.reload(); await expect(page).toHaveURL(runUrl); await expect(page.getByRole('heading', { name: 'Findings report', exact: true })).toBeVisible({ timeout: 20000 });
    await page.getByText('Compare evidence for GAP-0001', { exact: true }).click(); await capture(page, `gap-real-report-light-${width}`);
    const response = await page.request.get(runUrl.replace('/gap-check/', '/api/v1/gapcheck/'), { headers: { 'X-API-Key': writer } }); expect(response.status()).toBe(200); const job = await response.json() as Job;
    expect(job.status).toBe('completed'); expect(job.report?.counts_by_verdict.compliant).toBe(1); expect(job.report?.counts_by_verdict.addressed).toBe(1); expect(job.report?.counts_by_verdict.judge_failed).toBe(0);
    await mkdir(evidence, { recursive: true }); await writeFile(resolve(evidence, `fake-run-${width}.json`), JSON.stringify({ provider: 'fake', description: 'Actual app-factory job with real Postgres/Qdrant and scripted test-only judge; synthetic fixture, not a quality benchmark.', sop, browser_elapsed_ms: Date.now() - began, job }, null, 2) + '\n');
    await page.goto('/gap-check'); await page.getByRole('tab', { name: 'Upload file', exact: true }).click();
    await page.getByLabel('SOP file', { exact: true }).setInputFiles({ name: 'invalid.exe', mimeType: 'application/octet-stream', buffer: Buffer.from(source) }); await expect(page.getByRole('alert')).toContainText('Choose a PDF'); await capture(page, `gap-file-invalid-light-${width}`);
    await page.getByLabel('SOP file', { exact: true }).setInputFiles({ name: `synthetic-sop-${width}.md`, mimeType: 'text/markdown', buffer: Buffer.from(`# File cancellation ${width}\n\n${source}`) }); await capture(page, `gap-file-valid-light-${width}`);
    await page.getByRole('button', { name: 'Run gap check', exact: true }).click(); await expect(page.getByRole('button', { name: 'Cancel run', exact: true })).toBeVisible(); await page.getByRole('button', { name: 'Cancel run', exact: true }).click();
    await expect(page.getByText('Cancellation requested. Waiting for the server to confirm a terminal state.', { exact: true })).toBeVisible(); await capture(page, `gap-cancel-requested-light-${width}`);
    await expect(page.getByText('Run cancelled', { exact: true })).toBeVisible({ timeout: 15000 }); await capture(page, `gap-cancelled-light-${width}`);
  });
  test(`Gap all verdicts, URL filters, exports and print fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto(`/gap-check/${reportJob}`); await connected(page);
    await expect(page.getByRole('heading', { name: 'Findings report', exact: true })).toBeVisible(); await page.getByText('Compare evidence for GAP-0003', { exact: true }).click(); await page.getByText('Run details', { exact: true }).click();
    await expect(page.getByText('Manual review is required', { exact: true })).toBeVisible(); await expect(page.getByText('This run reached a limit', { exact: true })).toBeVisible(); await expect(page.locator('main script, main img')).toHaveCount(0); await capture(page, `gap-report-all-verdicts-light-${width}`);
    await page.getByLabel('Severity', { exact: true }).selectOption('high'); await page.getByLabel('Verdict', { exact: true }).selectOption('missing'); await expect(page.getByRole('article')).toHaveCount(1); await expect(page).toHaveURL(/severity=high&verdict=missing$/); await page.reload(); await expect(page.getByRole('article')).toHaveCount(1); await capture(page, `gap-report-filtered-light-${width}`);
    for (const format of ['JSON', 'Markdown']) {
      const pending = page.waitForEvent('download'); await page.getByRole('button', { name: format, exact: true }).click(); const download = await pending; const path = await download.path(); expect(path).not.toBeNull(); const contents = await readFile(path!, 'utf8');
      if (format === 'JSON') expect(JSON.parse(contents).findings).toHaveLength(8);
      else { expect(contents).toContain('Suggestion, not legal advice'); expect(contents).toContain('&lt;script&gt;'); expect(contents).not.toContain('<script>'); }
      if (width === 1280) await download.saveAs(resolve(evidence, `synthetic-report-export.${format === 'JSON' ? 'json' : 'md'}`));
    }
    await page.getByLabel('Search findings', { exact: true }).fill('No fixture phrase matches this'); await expect(page.getByText('No findings match these filters', { exact: true })).toBeVisible(); await capture(page, `gap-report-filter-empty-light-${width}`);
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click(); await page.getByLabel('Verdict', { exact: true }).selectOption('judge_failed'); await expect(page).toHaveURL(/\?verdict=judge_failed$/); await page.getByText('Compare evidence for GAP-0005', { exact: true }).click(); await capture(page, `gap-report-manual-review-light-${width}`);
    if (width === 1280) {
      await page.getByRole('button', { name: 'Clear filters', exact: true }).click(); await page.emulateMedia({ media: 'print' }); await page.evaluate(() => window.dispatchEvent(new Event('beforeprint'))); await capture(page, 'gap-report-print-1280');
      await page.pdf({ path: resolve(evidence, 'synthetic-report-print.pdf'), format: 'A4', printBackground: true }); await page.evaluate(() => window.dispatchEvent(new Event('afterprint'))); await page.emulateMedia({ media: 'screen' }); await expect(page.getByText('Compare evidence for GAP-0003', { exact: true }).locator('..')).not.toHaveAttribute('open');
    }
  });
  test(`Gap phases, polling error and terminal failures fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page);
    const now = new Date().toISOString(); let state: Job = { id: fixtureJob, status: 'running', progress: { phase: 'queued', clauses_total: 0, clauses_done: 0, requirements_total: 0, requirements_done: 0 }, report: null, error: null, created_at: now, started_at: now, finished_at: null }; let fail = false;
    await page.route(`**/api/v1/gapcheck/${fixtureJob}`, route => fail ? route.fulfill({ status: 503, json: { error: { code: 'fixture_poll_outage', message: 'Explicit browser polling fixture.', request_id: 'f4-poll-fixture' } } }) : route.fulfill({ json: state }));
    await page.goto(`/gap-check/${fixtureJob}`); await connected(page); await expect(page.getByText('Review in progress', { exact: true })).toBeVisible(); await capture(page, `gap-phase-queued-light-${width}`);
    state = { ...state, progress: { phase: 'requirements', clauses_total: 3, clauses_done: 3, requirements_total: 7, requirements_done: 2 } }; await page.reload(); await expect(page.getByText('Requirement 2 of 7', { exact: true })).toBeVisible(); await capture(page, `gap-phase-requirements-light-${width}`);
    fail = true; await expect(page.getByRole('alert')).toBeVisible({ timeout: 5000 }); await expect(page.getByText(/Status updates failed/)).toBeVisible(); await capture(page, `gap-poll-error-light-${width}`);
    fail = false; state = { ...state, progress: { ...state.progress, phase: 'finalizing', requirements_done: 7 } }; await page.reload(); await expect(page.getByText('Requirement 7 of 7', { exact: true })).toBeVisible(); await capture(page, `gap-phase-finalizing-light-${width}`);
    state = { ...state, status: 'failed', progress: { ...state.progress, phase: 'failed' }, error: 'Explicit browser fixture: the SOP could not be extracted.' }; await page.reload(); await expect(page.getByText('This run failed', { exact: true })).toBeVisible(); await capture(page, `gap-failed-light-${width}`);
    state = { ...state, status: 'completed', progress: { ...state.progress, phase: 'completed' }, error: null }; await page.reload(); await expect(page.getByText('The run finished without a report', { exact: true })).toBeVisible(); await capture(page, `gap-missing-report-light-${width}`);
    const fixtureResponse = await page.request.get(`/api/v1/gapcheck/${reportJob}`, { headers: { 'X-API-Key': writer } }); const fixture = await fixtureResponse.json() as Job;
    state = { ...state, report: { ...fixture.report!, job_id: fixtureJob, metadata: { model: { wrong: 'shape' }, token_usage: { total_tokens: 'wrong' } }, findings: [], sop_clauses: [], caps_hit: [], counts_by_verdict: {}, counts_by_severity: {}, counts_by_direction: {} } };
    await page.reload(); await expect(page.getByText('No findings returned', { exact: true })).toBeVisible(); await page.getByText('Run details', { exact: true }).click(); await capture(page, `gap-empty-report-metadata-light-${width}`);
    await page.goto('/gap-check'); await page.getByLabel('SOP text', { exact: true }).fill('Explicit input-cap browser fixture.');
    await page.route('**/api/v1/gapcheck', route => route.fulfill({ status: 422, json: { error: { code: 'clause_cap_exceeded', message: 'Explicit browser fixture: SOP has 81 clauses; the maximum is 80.', request_id: 'f4-input-cap-fixture' } } }));
    await page.getByRole('button', { name: 'Run gap check', exact: true }).click(); await expect(page.getByRole('alert')).toContainText('SOP has 81 clauses'); await capture(page, `gap-input-cap-error-light-${width}`);

  });
}
