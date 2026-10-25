import { test, expect } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { accessibilityCheck, keyboardNavigate, tabTo } from './accessibility.js';
import { capture, connected, evidenceDirectory, setup, writer } from './helpers.js';
import { source } from './fixtures.js';
import type { components } from '../src/types/api.js';
type Job = components['schemas']['GapCheckJobResponse'];

for (const width of [1280, 390, 360]) {
  test(`keyboard combined journey: Settings upload Search Ask citation Agent Gap exports ${width}px`, async ({ page }) => {
    test.setTimeout(90_000); await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/ask'); await tabTo(page, page.getByRole('link', { name: 'Open Settings', exact: true })); await page.keyboard.press('Enter');
    const key = page.getByLabel('API key', { exact: true }); await tabTo(page, key); await page.keyboard.insertText(writer); await tabTo(page, page.getByRole('button', { name: 'Validate key', exact: true })); await page.keyboard.press('Enter'); await connected(page);
    const checks: Record<string, unknown> = { settings: await accessibilityCheck(page) };
    await keyboardNavigate(page, 'Documents'); await tabTo(page, page.getByRole('button', { name: 'Upload document', exact: true })); await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog'); await expect(dialog.getByRole('button', { name: 'Close panel' })).toBeFocused(); await page.keyboard.press('Shift+Tab'); await expect(dialog.getByRole('button', { name: 'Start upload', exact: true })).toBeFocused();
    await dialog.getByLabel('Or choose a file').setInputFiles('e2e/files/sop.pdf');
    for (const [label, value] of [['Title', `F6 PDF journey ${width}`], ['Source agency', 'F6 workflow'], ['Document type', 'training'], ['Year', '2026'], ['Version', `v${width}`]]) { const field = dialog.getByLabel(label, { exact: true }); await tabTo(page, field); await page.keyboard.press('Control+A'); await page.keyboard.insertText(value); }
    checks.upload = await accessibilityCheck(page); await tabTo(page, dialog.getByRole('button', { name: 'Start upload', exact: true })); await page.keyboard.press('Enter'); await expect(page.getByRole('heading', { name: 'Document ingestion finished', exact: true })).toBeVisible(); await expect(page.getByRole('heading', { name: 'Document ingestion finished', exact: true })).toBeFocused();
    await capture(page, `journey-ingested-light-${width}`); checks.documents = await accessibilityCheck(page);
    await keyboardNavigate(page, 'Search library'); await tabTo(page, page.getByLabel('Search your library')); await page.keyboard.insertText(source); await tabTo(page, page.getByRole('button', { name: 'Search', exact: true })); await page.keyboard.press('Enter'); await expect(page.getByRole('heading', { name: /F6 PDF journey/ }).first()).toBeVisible(); checks.search = await accessibilityCheck(page); await capture(page, `journey-search-light-${width}`);
    await keyboardNavigate(page, 'Ask documents'); await tabTo(page, page.getByLabel('Your question')); await page.keyboard.insertText(source); await page.keyboard.press('Control+Enter'); await expect(page.getByRole('button', { name: 'Citations checked', exact: true })).toBeVisible();
    checks.ask = await accessibilityCheck(page); const chip = page.getByRole('button', { name: /^Source 1:/ }); await tabTo(page, chip); await page.keyboard.press('Enter'); await expect(page.getByRole('dialog', { name: 'Source excerpt' })).toBeVisible(); checks.source = await accessibilityCheck(page); await capture(page, `journey-citation-light-${width}`); await page.keyboard.press('Escape'); await expect(chip).toBeFocused();
    await keyboardNavigate(page, 'Research agent'); await tabTo(page, page.getByLabel('Research question')); await page.keyboard.insertText(source); await tabTo(page, page.getByRole('button', { name: 'Run agent', exact: true })); await page.keyboard.press('Enter'); await expect(page.getByRole('heading', { name: 'Execution trace', exact: true })).toBeVisible(); checks.agent = await accessibilityCheck(page); await capture(page, `journey-agent-light-${width}`);
    await keyboardNavigate(page, 'Gap check SOP'); await tabTo(page, page.getByLabel('SOP text', { exact: true })); await page.keyboard.insertText(source); await tabTo(page, page.getByRole('button', { name: 'Run gap check', exact: true })); await page.keyboard.press('Enter'); await expect(page.getByRole('heading', { name: 'Findings report', exact: true })).toBeVisible();
    await tabTo(page, page.getByLabel('Verdict', { exact: true })); await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter'); await expect(page.getByRole('article').first()).toBeVisible(); checks.gap = await accessibilityCheck(page); await capture(page, `journey-report-light-${width}`);
    const exports: string[] = [];
    for (const format of ['JSON', 'Markdown']) { const pending = page.waitForEvent('download'); await tabTo(page, page.getByRole('button', { name: format, exact: true })); await page.keyboard.press('Enter'); const download = await pending; const path = await download.path(); const content = await readFile(path!, 'utf8'); expect(content).toContain('Decision support'); exports.push(format); }
    await tabTo(page, page.getByRole('button', { name: 'Switch to dark theme', exact: true })); await page.keyboard.press('Enter'); await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark'); checks.dark_report = await accessibilityCheck(page); await capture(page, `journey-report-dark-${width}`);
    for (const [name, path] of [['Ask documents', 'ask'], ['Search library', 'search'], ['Research agent', 'agent'], ['Gap check SOP', 'gap-check'], ['Documents', 'documents'], ['Settings', 'settings']]) {
      await keyboardNavigate(page, name); checks[`dark_${path}`] = await accessibilityCheck(page); await capture(page, `accessibility-${path}-dark-${width}`);
    }
    await page.goto('/gap-check/10000000-0000-4000-8000-000000000006'); await expect(page.getByRole('article')).toHaveCount(8); checks.dark_all_verdicts = await accessibilityCheck(page); await capture(page, `accessibility-verdicts-dark-${width}`);
    await page.route('**/api/v1/search', route => route.fulfill({ status: 503, json: { error: { code: 'accessibility_error_fixture', message: 'Explicit accessibility error fixture.', request_id: 'f6-a11y-error' } } }));
    await keyboardNavigate(page, 'Search library'); await tabTo(page, page.getByLabel('Search your library')); await page.keyboard.insertText(source); await tabTo(page, page.getByRole('button', { name: 'Search', exact: true })); await page.keyboard.press('Enter'); await expect(page.getByRole('alert')).toBeVisible();
    const errorCheck = await accessibilityCheck(page); expect(errorCheck.live_regions.some(region => region.role === 'alert' && region.live === 'assertive')).toBe(true); checks.dark_error = errorCheck; await capture(page, `accessibility-error-dark-${width}`);
    const transitions = await page.getByRole('button', { name: 'Search', exact: true }).evaluate(element => getComputedStyle(element).transitionDuration); expect(transitions).toBe('0s');
    await mkdir(evidenceDirectory, { recursive: true }); await writeFile(resolve(evidenceDirectory, `keyboard-accessibility-${width}.json`), JSON.stringify({ width, checks, exports, reduced_motion: true, scope: 'Keyboard controls and Chromium accessibility tree/contrast; no claim of a human screen-reader session or WCAG certification.' }, null, 2) + '\n');
  });
  for (const extension of ['pdf', 'txt']) test(`real ${extension.toUpperCase()} document and SOP upload, progress, report and export ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 }); await setup(page); await page.goto('/documents'); await connected(page); await page.getByRole('button', { name: 'Upload document', exact: true }).click(); const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Or choose a file').setInputFiles(`e2e/files/sop-${width}.${extension}`);
    for (const [label, value] of [['Title', `F6 ${extension.toUpperCase()} file ${width}`], ['Source agency', 'F6 file journey'], ['Document type', 'training'], ['Year', '2026'], ['Version', `v${width}`]]) await dialog.getByLabel(label, { exact: true }).fill(value);
    await dialog.getByRole('button', { name: 'Start upload', exact: true }).click(); await expect(page.getByText('Document ingestion finished', { exact: true })).toBeVisible(); await capture(page, `file-${extension}-ingested-${width}`);
    await page.goto('/gap-check'); await page.getByRole('tab', { name: 'Upload file', exact: true }).click(); await page.getByLabel('SOP file', { exact: true }).setInputFiles(`e2e/files/sop-${width}.${extension}`); await capture(page, `file-${extension}-gap-input-${width}`);
    await page.getByRole('button', { name: 'Run gap check', exact: true }).click(); await expect(page.getByText('Review in progress', { exact: true })).toBeVisible(); await capture(page, `file-${extension}-gap-progress-${width}`); await page.reload(); await expect(page.getByRole('heading', { name: 'Findings report', exact: true })).toBeVisible();
    const jobId = page.url().split('/').at(-1)!; const response = await page.request.get(`/api/v1/gapcheck/${jobId}`, { headers: { 'X-API-Key': writer } }); const job = await response.json() as Job;
    expect(job.status).toBe('completed'); expect(job.report?.sop_clauses.some(clause => clause.text.includes('instrument checks'))).toBe(true); expect(job.report?.findings.length).toBeGreaterThan(0);
    await page.getByText(/^Compare evidence for GAP-/).first().click(); await capture(page, `file-${extension}-gap-report-${width}`);
    for (const format of ['JSON', 'Markdown']) { const pending = page.waitForEvent('download'); await page.getByRole('button', { name: format, exact: true }).click(); const path = await (await pending).path(); const content = await readFile(path!, 'utf8'); if (format === 'JSON') expect(JSON.parse(content)).toEqual(job.report); else expect(content).toContain('instrument checks'); }
    await mkdir(evidenceDirectory, { recursive: true }); await writeFile(resolve(evidenceDirectory, `file-${extension}-${width}.json`), JSON.stringify({ description: 'Actual document and SOP file uploads using app factory, real isolated stores and deterministic test-only LLM. Synthetic text, no quality claim.', job }, null, 2) + '\n');
  });
}
