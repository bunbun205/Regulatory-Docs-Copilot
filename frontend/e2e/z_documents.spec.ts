import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { components } from '../src/types/api.js';
import { capture, connected, evidenceDirectory, reader, setup, writer } from './helpers.js';

type Document = components['schemas']['DocumentSummary'];
type Job = components['schemas']['IngestionJobResponse'];
const fixtureDocuments: Document[] = Array.from({ length: 12 }, (_, i) => ({ id: `20000000-0000-4000-8000-${String(i).padStart(12, '0')}`, title: `Synthetic library document ${String(i + 1).padStart(2, '0')}`, source_agency: 'Fixture agency', doc_type: 'guidance', year: 2020 + i % 6, version: 'v1', filename: `document-${i + 1}.md`, page_count: 1, created_at: '2026-10-26T00:00:00Z' }));
const fixtureId = '30000000-0000-4000-8000-000000000001';
const fixtureReport = { documents_total: 4, documents_ingested: 1, documents_updated: 0, documents_duplicate: 1, documents_metadata_updated: 1, documents_failed: 1, chunks: 3, documents: [{ filename: 'synthetic-good.md', document_id: fixtureDocuments[0].id, chunks: 3 }], updates: [], duplicates: [{ filename: 'synthetic-duplicate.md', document_id: fixtureDocuments[1].id, metadata_updated: ['title'] }], metadata_updates: [{ filename: 'synthetic-duplicate.md', changed_fields: ['title'] }], failures: [{ filename: '<script>quoted filename</script>.pdf', reason: 'Postgres committed this document, but the qdrant index is out of date. Run reindex.' }], rejected_rows: [{ row: 4, filename: 'synthetic-invalid.md', reasons: ['Required title is missing.', 'Year is invalid.'] }], duration_ms: 1250 };
async function fillUpload(page: Page, title: string, width: number) {
  await page.getByRole('button', { name: 'Upload document', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const contents = `# Synthetic F5 upload ${width}\n\nStaff must retain the training record for instrument checks.\n\nThis document is a browser test fixture for width ${width}.`;
  if (width === 390) await dialog.getByText('Drop one document here', { exact: true }).evaluate((element, file) => { const data = new DataTransfer(); data.items.add(new File([file.contents], file.name, { type: 'text/markdown' })); element.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: data })); }, { name: `f5-browser-${width}.md`, contents });
  else await dialog.getByLabel('Or choose a file').setInputFiles({ name: `f5-browser-${width}.md`, mimeType: 'text/markdown', buffer: Buffer.from(contents) });
  expect(await dialog.getByLabel('Or choose a file').evaluate((element: HTMLInputElement) => element.files?.length)).toBe(1);
  await dialog.getByLabel('Title', { exact: true }).fill(title); await dialog.getByLabel('Source agency', { exact: true }).fill('F5 browser fixture'); await dialog.getByLabel('Document type', { exact: true }).fill('training'); await dialog.getByLabel('Year', { exact: true }).fill('2026'); await dialog.getByLabel('Version', { exact: true }).fill('v1');
}

for (const width of [1280, 390, 360]) {
  test(`Documents table, page search, filters, pagination and failures fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page);
    let outage = false; let countsFail = false; let empty = false; let pending = false; let release: (() => void) | undefined;
    await page.route('**/api/v1/documents?*', async route => {
      if (pending) await new Promise<void>(resolve => { release = resolve; });
      if (outage) return route.fulfill({ status: 503, json: { error: { code: 'f5-list-fixture', message: 'Explicit document list outage fixture.', request_id: 'f5-list-fixture' } } });
      const params = new URL(route.request().url()).searchParams; const offset = Number(params.get('offset')); const limit = Number(params.get('limit')); const filtered = empty ? [] : params.has('source_agency') ? fixtureDocuments.slice(0, 2) : fixtureDocuments;
      return route.fulfill({ json: { items: filtered.slice(offset, offset + limit), total: filtered.length } });
    });
    await page.route('**/api/v1/documents/*', async route => {
      const id = route.request().url().split('/').at(-1); const document = fixtureDocuments.find(item => item.id === id)!;
      return countsFail ? route.fulfill({ status: 503, json: { error: { code: 'f5-count-fixture', message: 'Explicit chunk count outage.' } } }) : route.fulfill({ json: { ...document, chunk_count: 4 } });
    });
    await page.goto('/documents'); await connected(page); await expect(page.getByText('Loaded 1–10 of 12 documents', { exact: true })).toBeVisible(); await expect(page.getByLabel('Loading chunk count')).toHaveCount(0); await capture(page, `documents-table-light-${width}`);
    if (width < 500) { const table = page.getByRole('region', { name: 'Document library table' }); await table.evaluate(element => { element.scrollLeft = element.scrollWidth; }); await capture(page, `documents-table-scrolled-light-${width}`); }
    await page.getByLabel('Sort this page').selectOption('title-desc'); await expect(page.getByRole('row').nth(1)).toContainText('document 10'); await capture(page, `documents-sorted-light-${width}`);
    await page.getByLabel('Search titles on this page').fill('document 12'); await expect(page.getByText('No titles match on this page', { exact: true })).toBeVisible(); await capture(page, `documents-title-empty-light-${width}`);
    await page.getByRole('button', { name: 'Next page', exact: true }).click(); await expect(page.getByText('Synthetic library document 12', { exact: true })).toBeVisible(); await capture(page, `documents-page-two-light-${width}`); await page.getByLabel('Search titles on this page').fill('');
    await page.getByText('Filter the library', { exact: true }).click(); await page.getByLabel('Agency', { exact: true }).fill('Fixture agency'); await page.getByLabel('Start year').fill('2026'); await page.getByLabel('End year').fill('2020'); await expect(page.getByRole('alert')).toContainText('Start year'); await capture(page, `documents-filter-invalid-light-${width}`);
    await page.getByLabel('Start year').fill('2020'); await page.getByLabel('End year').fill('2026'); await page.getByRole('button', { name: 'Apply filters', exact: true }).click(); await expect(page.getByText('Loaded 1–2 of 2 documents', { exact: true })).toBeVisible(); await capture(page, `documents-filtered-light-${width}`);
    await page.getByRole('button', { name: 'Remove Agency filter', exact: true }).click(); await expect(page.getByText('Loaded 1–10 of 12 documents', { exact: true })).toBeVisible();
    countsFail = true; await page.getByRole('button', { name: 'Refresh', exact: true }).click(); await expect(page.getByText(/Some chunk counts could not be loaded/)).toBeVisible(); await capture(page, `documents-count-error-light-${width}`); countsFail = false; await page.getByRole('button', { name: 'Retry chunk counts', exact: true }).click(); await expect(page.getByText(/Some chunk counts could not be loaded/)).toHaveCount(0);
    outage = true; await page.getByRole('button', { name: 'Refresh', exact: true }).click(); await expect(page.getByRole('alert')).toBeVisible(); await capture(page, `documents-list-error-light-${width}`); outage = false; await page.getByRole('button', { name: 'Retry', exact: true }).click(); await expect(page.getByRole('alert')).toHaveCount(0);
    empty = true; await page.getByRole('button', { name: 'Clear filters', exact: true }).click(); await expect(page.getByText('Your library is empty', { exact: true })).toBeVisible(); await capture(page, `documents-empty-light-${width}`);
    empty = false; pending = true; await page.reload(); await expect(page.getByLabel('Loading', { exact: true })).toBeVisible(); await capture(page, `documents-loading-light-${width}`); pending = false; release?.(); await expect(page.getByRole('table')).toBeVisible();
  });
  test(`Documents real Markdown upload and duplicate metadata update fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/documents'); await connected(page);
    await page.getByRole('button', { name: 'Upload document', exact: true }).click(); const dialog = page.getByRole('dialog'); await expect(dialog.getByRole('button', { name: 'Close panel' })).toBeFocused(); await capture(page, `documents-upload-empty-light-${width}`);
    await dialog.getByLabel('Or choose a file').setInputFiles({ name: 'invalid.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('invalid') }); await dialog.getByRole('button', { name: 'Start upload', exact: true }).click(); await expect(dialog.getByRole('alert').first()).toBeVisible(); await capture(page, `documents-upload-invalid-light-${width}`);
    await page.keyboard.press('Escape'); await expect(page.getByRole('button', { name: 'Upload document', exact: true })).toBeFocused();
    for (const duplicate of [false, true]) {
      await fillUpload(page, `F5 browser upload ${width}${duplicate ? ' updated metadata' : ''}`, width); if (duplicate) await page.getByRole('dialog').getByLabel('Version', { exact: true }).fill('v2');
      if (!duplicate) { await capture(page, `documents-upload-ready-light-${width}`); await page.getByRole('dialog').getByRole('button', { name: 'Start upload', exact: true }).scrollIntoViewIfNeeded(); await capture(page, `documents-upload-actions-light-${width}`); }
      const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/documents') && response.request().method() === 'POST'); const began = Date.now(); await page.getByRole('dialog').getByRole('button', { name: 'Start upload', exact: true }).click(); const response = await responsePromise; expect(response.status()).toBe(202); const { job_id } = await response.json() as { job_id: string };
      await expect(page.getByText('Document ingestion finished', { exact: true })).toBeVisible(); await expect(page.getByRole('heading', { name: 'Document ingestion finished', exact: true })).toBeFocused(); await expect(page.getByText('Ingestion report', { exact: true })).toBeVisible(); const result = await page.request.get(`/api/v1/jobs/${job_id}`, { headers: { 'X-API-Key': writer } }); const job = await result.json() as Job; expect(job.status).toBe('completed'); expect(job.error).toBeNull(); expect(job.report?.documents_duplicate).toBe(duplicate ? 1 : 0); expect(job.report?.documents_metadata_updated).toBe(duplicate ? 1 : 0);
      if (!duplicate) expect(Number(job.report?.chunks)).toBeGreaterThan(0);
      await page.getByText('Document and metadata details', { exact: true }).click(); await capture(page, `documents-${duplicate ? 'duplicate-report' : 'actual-report'}-light-${width}`);
      await mkdir(evidenceDirectory, { recursive: true }); await writeFile(resolve(evidenceDirectory, `document-${duplicate ? 'duplicate' : 'upload'}-${width}.json`), JSON.stringify({ description: 'Actual upload through Vite proxy and app factory with isolated Postgres/Qdrant and deterministic embedder.', browser_elapsed_ms: Date.now() - began, job }, null, 2) + '\n');
    }
  });
  test(`Documents progress, poll recovery, partial and sync failure fixtures fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page);
    let outage = false; let uploads = 0; const now = new Date().toISOString(); let job: Job = { id: fixtureId, status: 'running', created_at: now, started_at: now, finished_at: null, report: null, error: null };
    await page.route('**/api/v1/documents', route => route.fulfill({ status: 202, json: { job_id: `${fixtureId.slice(0, -1)}${++uploads}` } }));
    await page.route('**/api/v1/jobs/*', route => outage ? route.fulfill({ status: 503, json: { error: { code: 'f5-poll-fixture', message: 'Explicit ingestion polling outage fixture.', request_id: 'f5-poll-fixture' } } }) : route.fulfill({ json: job }));
    await page.goto('/documents'); await connected(page); await fillUpload(page, 'Explicit ingestion lifecycle browser fixture', width); await page.getByRole('dialog').getByRole('button', { name: 'Start upload', exact: true }).click(); await expect(page.getByText('running', { exact: true })).toBeVisible(); await capture(page, `documents-progress-fixture-light-${width}`);
    outage = true; await expect(page.getByRole('alert')).toBeVisible({ timeout: 6000 }); await capture(page, `documents-poll-error-light-${width}`); outage = false; job = { ...job, status: 'completed', finished_at: now, report: fixtureReport }; await page.getByRole('button', { name: 'Retry', exact: true }).click(); await expect(page.getByText('Some documents need attention', { exact: true })).toBeVisible(); await expect(page.getByText('Qdrant needs to be rebuilt', { exact: true })).toBeVisible(); await expect(page.locator('script').filter({ hasText: 'quoted filename' })).toHaveCount(0); await page.getByText('Document and metadata details', { exact: true }).click(); await capture(page, `documents-partial-sync-report-light-${width}`);
    await page.getByText('Full ingestion report', { exact: true }).click(); await capture(page, `documents-full-report-light-${width}`);
    job = { ...job, id: fixtureId.slice(0, -1) + '2', status: 'failed', report: null, error: 'Explicit browser fixture: the PDF could not be read.' }; await fillUpload(page, 'Explicit failed ingestion browser fixture', width); await page.getByRole('dialog').getByRole('button', { name: 'Start upload', exact: true }).click(); await expect(page.getByText('Document ingestion failed', { exact: true })).toBeVisible(); await capture(page, `documents-failed-light-${width}`);
    await page.getByRole('button', { name: 'Upload document', exact: true }).click(); await page.route('**/api/v1/documents', route => route.fulfill({ status: 413, json: { error: { code: 'payload_too_large', message: 'Explicit browser fixture: server upload limit exceeded.', request_id: 'f5-upload-fixture' } } })); await page.getByRole('dialog').getByRole('button', { name: 'Start upload', exact: true }).click(); await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible(); await capture(page, `documents-upload-server-error-light-${width}`);
  });
  test(`Documents read-only scope and dark library fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page, reader); await page.goto('/documents'); await expect(page.getByText(/This key is read only/)).toBeVisible(); await expect(page.getByRole('button', { name: 'Upload document', exact: true })).toHaveCount(0); await capture(page, `documents-read-only-light-${width}`);
    await page.getByRole('button', { name: 'Switch to dark theme', exact: true }).click(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark'); await capture(page, `documents-dark-${width}`);
  });
}
