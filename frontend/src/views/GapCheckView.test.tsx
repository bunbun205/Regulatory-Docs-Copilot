/// <reference types="node" />
import { File as NodeFile } from 'node:buffer';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import GapCheckView from './GapCheckView';
import GapReport from '../components/gap/GapReport';
import { mockResearch, mountResearch } from '../test/research';
import { gapJob, gapReport } from '../test/gap';
function Location() { return <output aria-label="Current URL">{useLocation().search}</output>; }
function mount(route = '/gap-check') { return mountResearch(<Routes><Route path="/gap-check" element={<GapCheckView />} /><Route path="/gap-check/:jobId" element={<GapCheckView />} /></Routes>, route); }
function handler(request: Request) { if (request.url.includes('/documents?')) return Response.json({ items: [], total: 0 }); return Response.json(gapJob); }
describe('Gap input and lifecycle', () => {
  it('submits valid paste text and scope as multipart, navigates and resumes progress', async () => {
    let posted: FormData | null = null;
    mockResearch(async request => { if (request.method === 'POST') { posted = await request.formData(); return Response.json({ job_id: 'job-a', status: 'queued' }); } return handler(request); });
    mount(); await screen.findByText('0 documents match these filters.'); fireEvent.change(screen.getByLabelText('SOP text'), { target: { value: 'Staff must record instrument checks.' } });
    await userEvent.click(screen.getByRole('button', { name: 'Run gap check' })); await screen.findByText('Review in progress'); expect((posted as FormData | null)?.get('text')).toBe('Staff must record instrument checks.'); expect((posted as FormData | null)?.get('backend')).toBe('pgvector'); expect(screen.getByText('Clause 1 of 2')).toBeTruthy(); expect(screen.getByRole('button', { name: 'Cancel run' })).toBeTruthy();
  });
  it('validates file input locally and sends only the file in upload mode', async () => {
    // Node fetch needs its native File/FormData pair; browser uploads are also exercised in Playwright.
    const nativeForm = await new Response('', { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }).formData();
    vi.stubGlobal('FormData', nativeForm.constructor); vi.stubGlobal('File', NodeFile);
    const posts: FormData[] = []; mockResearch(async request => { if (request.method === 'POST') { posts.push(await request.formData()); return Response.json({ job_id: 'job-a', status: 'queued' }); } return handler(request); });
    mount(); await userEvent.click(screen.getByRole('tab', { name: 'Upload file' })); const file = screen.getByLabelText('SOP file'); fireEvent.change(file, { target: { files: [new File(['bad'], 'sop.exe')] } }); expect(screen.getByRole('alert').textContent).toMatch(/PDF/); expect(screen.getByRole('button', { name: 'Run gap check' }).hasAttribute('disabled')).toBe(true);
    fireEvent.change(file, { target: { files: [new File(['Staff must record checks.'], 'sop.md', { type: 'text/markdown' })] } }); await userEvent.click(screen.getByRole('button', { name: 'Run gap check' })); await screen.findByText('Review in progress'); expect(posts).toHaveLength(1); expect(posts[0].has('file')).toBe(true); expect(posts[0].has('text')).toBe(false);
  });
  it('shows input cap errors from the API and keeps retry/details visible', async () => {
    mockResearch(async request => request.method === 'POST' ? Response.json({ error: { code: 'clause_cap_exceeded', message: 'SOP has 81 clauses; maximum 80.', request_id: 'cap-test' } }, { status: 422 }) : handler(request)); mount(); fireEvent.change(screen.getByLabelText('SOP text'), { target: { value: 'A procedure.' } }); fireEvent.submit(screen.getByLabelText('SOP text').closest('form')!);
    await screen.findByRole('alert'); expect(screen.getByRole('alert').textContent).toContain('SOP has 81 clauses'); expect(screen.getByRole('button', { name: 'Copy details' })).toBeTruthy();
  });
  it('keeps a cancellation request distinct from server-confirmed cancellation', async () => {
    vi.useFakeTimers(); let cancelled = false;
    mockResearch(async request => request.method === 'POST' ? (cancelled = true, Response.json({ job_id: 'job-a', cancel_requested: true })) : Response.json(cancelled ? { ...gapJob, status: 'cancelled', progress: { ...gapJob.progress, phase: 'cancelled' } } : gapJob));
    mount('/gap-check/job-a'); await act(async () => {}); fireEvent.click(screen.getByRole('button', { name: 'Cancel run' })); await act(async () => {}); expect(screen.getByText('Cancellation requested. Waiting for the server to confirm a terminal state.')).toBeTruthy(); expect(screen.queryByText('Run cancelled')).toBeNull(); await act(async () => vi.advanceTimersByTimeAsync(2000)); expect(screen.getByText('Run cancelled')).toBeTruthy(); expect(screen.queryByRole('button', { name: 'Cancel run' })).toBeNull();
  });
  it('exposes polling failure without discarding the last known progress', async () => {
    vi.useFakeTimers(); let calls = 0; mockResearch(async () => ++calls === 1 ? Response.json(gapJob) : Response.json({ error: { code: 'unavailable', message: 'Poll outage' } }, { status: 503 }));
    mount('/gap-check/job-a'); await act(async () => {}); await act(async () => vi.advanceTimersByTimeAsync(2000)); expect(screen.getByRole('alert')).toBeTruthy(); expect(screen.getByText(/Status updates failed/)).toBeTruthy(); expect(screen.getByText('Clause 1 of 2')).toBeTruthy();
  });
  it.each(['failed', 'cancelled'] as const)('explains a terminal %s run without a report', async status => {
    mockResearch(async () => Response.json({ ...gapJob, status, error: status === 'failed' ? 'Failed to extract SOP text.' : 'Gap check cancelled.' })); mount('/gap-check/job-a'); await screen.findByText('No report is available for this run'); expect(screen.queryByRole('button', { name: 'Cancel run' })).toBeNull(); if (status === 'cancelled') expect(screen.queryByRole('alert')).toBeNull();
  });
  it('shows a completed report when the bookmarked job URL is opened', async () => {
    mockResearch(async () => Response.json({ ...gapJob, status: 'completed', report: gapReport })); mount('/gap-check/job-a'); await screen.findByText('Findings report'); expect(screen.getByText(gapReport.banner)).toBeTruthy(); expect(screen.queryByText('Review in progress')).toBeNull();
  });
});
describe('Gap report review', () => {
  it('filters with the URL and restores a direct filtered link', async () => {
    mockResearch(async () => Response.json({})); mountResearch(<><GapReport report={gapReport} /><Location /></>, '/gap-check/job-a?verdict=judge_failed'); expect(screen.getAllByRole('article')).toHaveLength(1); expect(screen.getByRole('article').getAttribute('aria-label')).toContain('Needs manual review');
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' })); expect(screen.getAllByRole('article')).toHaveLength(3); await userEvent.selectOptions(screen.getByLabelText('Severity'), 'high'); expect(screen.getByLabelText('Current URL').textContent).toBe('?severity=high'); expect(screen.getAllByRole('article')).toHaveLength(1); fireEvent.change(screen.getByLabelText('Search findings'), { target: { value: 'no match' } }); expect(screen.getByText('No findings match these filters')).toBeTruthy();
  });
  it('does not restore cleared URL filters during a rapid next selection', () => {
    mockResearch(async () => Response.json({})); mountResearch(<><GapReport report={gapReport} /><Location /></>, '/gap-check/job-a?severity=high&q=old');
    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Clear filters' })); fireEvent.change(screen.getByLabelText('Verdict'), { target: { value: 'judge_failed' } }); });
    expect(screen.getByLabelText('Current URL').textContent).toBe('?verdict=judge_failed'); expect(screen.getAllByRole('article')).toHaveLength(1);
  });
  it('keeps judge failure unresolved and puts outside-corpus findings in a neutral group', () => {
    mockResearch(async () => Response.json({})); mountResearch(<GapReport report={gapReport} />); expect(screen.getByText('Manual review is required')).toBeTruthy(); expect(screen.getByText(/never treated as passes/)).toBeTruthy(); const outside = screen.getByRole('region', { name: 'Outside the loaded documents' }); expect(within(outside).getByRole('article').getAttribute('aria-label')).toContain('GAP-0003');
  });
  it('renders SOP/model/snippet strings as text and exposes comparison and suggestions', async () => {
    mockResearch(async () => Response.json({})); const hostile = '<img src=x onerror=alert(1)>'; const report = { ...gapReport, findings: [{ ...gapReport.findings[0], rationale: hostile, suggested_fix: hostile, regulation_citations: [{ ...gapReport.findings[0].regulation_citations[0], snippet: '<script>bad()</script>' }] }], sop_clauses: [{ ...gapReport.sop_clauses[1], text: hostile }] };
    const { container } = mountResearch(<GapReport report={report} />); await userEvent.click(screen.getByText('Compare evidence for GAP-0001')); expect(screen.getByText('Suggestion, not legal advice')).toBeTruthy(); expect(screen.getByText('<script>bad()</script>')).toBeTruthy(); expect(container.querySelector('img,script')).toBeNull();
  });
  it('shows empty reports, reported caps and missing metadata honestly', () => {
    mockResearch(async () => Response.json({})); mountResearch(<GapReport report={{ ...gapReport, findings: [], metadata: {}, caps_hit: ['requirements'] }} />); expect(screen.getByText('No findings returned')).toBeTruthy(); expect(screen.getByText('This run reached a limit')).toBeTruthy(); expect(screen.queryByText('fake:unit-fixture')).toBeNull(); expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
  });
  it('opens current and newly mounted comparisons across print events, then restores them', async () => {
    mockResearch(async () => Response.json({})); const { container } = mountResearch(<GapReport report={gapReport} />, '/gap-check/job-a?verdict=judge_failed');
    await act(async () => window.dispatchEvent(new Event('beforeprint')));
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' })); expect(screen.getAllByRole('article')).toHaveLength(3);
    await act(async () => window.dispatchEvent(new Event('beforeprint'))); const details = Array.from(container.querySelectorAll('details')); expect(details.every(element => element.open)).toBe(true);
    await act(async () => window.dispatchEvent(new Event('afterprint'))); await waitFor(() => expect(details.every(element => !element.open)).toBe(true));
  });
});
