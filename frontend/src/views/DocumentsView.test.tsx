/// <reference types="node" />
import { File as NodeFile } from 'node:buffer';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import DocumentsView from './DocumentsView';
import { mountResearch } from '../test/research';
import { document, ingestionJob } from '../test/documents';
import type { Document } from '../domain/documents';

function mockDocuments(handler: (request: Request) => Promise<Response>, write = false) {
  const fetcher = vi.fn(async (request: Request) => {
    if (request.url.endsWith('/whoami')) return Response.json({ name: 'document-reader', scopes: write ? ['read', 'write'] : ['read'] });
    if (request.url.endsWith('/readyz')) return Response.json({ status: 'ok', checks: { database: 'ok' } });
    return handler(request);
  }); vi.stubGlobal('fetch', fetcher); return fetcher;
}
function list(items: Document[] = [document], total = items.length) { return Response.json({ items, total }); }
function detail(item = document, chunk_count = 7) { return Response.json({ ...item, chunk_count }); }
const records = Array.from({ length: 12 }, (_, i) => ({ ...document, id: `doc-${i}`, title: `Document ${String(i).padStart(2, '0')}` }));
function paginated(request: Request) { const url = new URL(request.url); return list(records.slice(Number(url.searchParams.get('offset')), Number(url.searchParams.get('offset')) + Number(url.searchParams.get('limit'))), 12); }
async function fillUpload() {
  const nativeForm = await new Response('', { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }).formData(); vi.stubGlobal('FormData', nativeForm.constructor); vi.stubGlobal('File', NodeFile);
  await screen.findByRole('button', { name: 'Upload document' }); fireEvent.click(screen.getByRole('button', { name: 'Upload document' }));
  fireEvent.change(screen.getByLabelText('Or choose a file'), { target: { files: [new File(['Staff must record checks.'], 'checks.md', { type: 'text/markdown' })] } });
  for (const [label, value] of [['Title', ' Checks '], ['Source agency', ' Agency '], ['Document type', 'training'], ['Year', '2026'], ['Version', 'v2']]) fireEvent.change(within(screen.getByRole('dialog')).getByLabelText(label, { exact: true }), { target: { value } });
}

describe('Documents library', () => {
  it('browses with read scope while hiding upload controls', async () => {
    mockDocuments(async request => request.url.includes('/documents?') ? list() : detail()); mountResearch(<DocumentsView />);
    await screen.findByRole('table'); await screen.findByText(/This key is read only/); expect(screen.queryByRole('button', { name: 'Upload document' })).toBeNull(); expect(screen.getByRole('columnheader', { name: 'Chunks' })).toBeTruthy();
  });
  it('uses server pagination and metadata filters, and resets the offset when filters change', async () => {
    const urls: URL[] = []; mockDocuments(async request => { if (request.url.includes('/documents?')) { urls.push(new URL(request.url)); return paginated(request); } return detail(); }); mountResearch(<DocumentsView />);
    await screen.findByText('Loaded 1–10 of 12 documents'); await userEvent.click(screen.getByRole('button', { name: 'Next page' })); await screen.findByText('Loaded 11–12 of 12 documents');
    await userEvent.click(screen.getByText('Filter the library')); fireEvent.change(screen.getByLabelText('Agency'), { target: { value: 'FDA' } }); fireEvent.change(screen.getByLabelText('Start year'), { target: { value: '2020' } }); await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    await screen.findByText('Loaded 1–10 of 12 documents'); expect(urls.at(-1)?.searchParams.get('source_agency')).toBe('FDA'); expect(urls.at(-1)?.searchParams.get('year_min')).toBe('2020'); expect(urls.at(-1)?.searchParams.get('offset')).toBe('0');
    await userEvent.click(screen.getByRole('button', { name: 'Remove Agency filter' })); await waitFor(() => expect(urls.at(-1)?.searchParams.has('source_agency')).toBe(false)); expect(urls.at(-1)?.searchParams.get('year_min')).toBe('2020');
  });
  it('keeps title search and sorting on the loaded page and does not send nonexistent API parameters', async () => {
    const urls: string[] = []; mockDocuments(async request => { if (request.url.includes('/documents?')) { urls.push(request.url); return paginated(request); } return detail(); }); mountResearch(<DocumentsView />); await screen.findByRole('table');
    fireEvent.change(screen.getByLabelText('Search titles on this page'), { target: { value: 'Document 11' } }); expect(screen.getByText('No titles match on this page')).toBeTruthy(); expect(urls).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('Search titles on this page'), { target: { value: '' } }); await userEvent.selectOptions(screen.getByLabelText('Sort this page'), 'title-desc'); expect(within(screen.getByRole('table')).getAllByRole('row')[1].textContent).toContain('Document 09'); expect(urls).toHaveLength(1);
    await userEvent.click(screen.getByText('Filter the library')); fireEvent.change(screen.getByLabelText('Start year'), { target: { value: '2027' } }); fireEvent.change(screen.getByLabelText('End year'), { target: { value: '2026' } }); expect(screen.getByRole('button', { name: 'Apply filters' }).hasAttribute('disabled')).toBe(true); expect(screen.getByRole('alert').textContent).toContain('Start year');
  });
  it('limits concurrent detail requests to three and caches counts across page changes', async () => {
    let active = 0; let peak = 0; let details = 0; const release: (() => void)[] = [];
    mockDocuments(async request => {
      if (request.url.includes('/documents?')) return paginated(request);
      active++; details++; peak = Math.max(peak, active);
      await new Promise<void>(resolve => release.push(() => { active--; resolve(); })); return detail();
    }); mountResearch(<DocumentsView />); await screen.findByRole('table'); await waitFor(() => expect(active).toBe(3));
    while (details < 10 || active > 0) { await act(async () => { release.splice(0).forEach(resolve => resolve()); }); }
    expect(peak).toBe(3); expect(details).toBe(10); await userEvent.click(screen.getByRole('button', { name: 'Next page' })); await screen.findByText('Loaded 11–12 of 12 documents'); await waitFor(() => expect(active).toBe(2));
    await act(async () => { release.splice(0).forEach(resolve => resolve()); }); await userEvent.click(screen.getByRole('button', { name: 'Previous page' })); await screen.findByText('Loaded 1–10 of 12 documents'); await waitFor(() => expect(screen.queryByLabelText('Loading chunk count')).toBeNull()); expect(details).toBe(12);
  });
  it('retains library metadata when a count fails and supports retry without reporting a false zero', async () => {
    let failed = true; mockDocuments(async request => request.url.includes('/documents?') ? list() : failed ? Response.json({ error: { code: 'detail_unavailable', message: 'Detail outage' } }, { status: 503 }) : detail()); mountResearch(<DocumentsView />);
    await screen.findByText(/Some chunk counts could not be loaded/); expect(screen.getByText('Instrument checks')).toBeTruthy(); expect(screen.getByTitle('Chunk count could not be loaded').textContent).toBe('—'); failed = false; await userEvent.click(screen.getByRole('button', { name: 'Retry chunk counts' })); await screen.findByRole('cell', { name: '7' }); expect(screen.queryByTitle('Chunk count could not be loaded')).toBeNull();
  });
  it('explains list errors and supports a successful refresh', async () => {
    let failed = true; mockDocuments(async request => request.url.includes('/documents?') && failed ? Response.json({ error: { code: 'outage', message: 'Unavailable' } }, { status: 503 }) : request.url.includes('/documents?') ? list() : detail()); mountResearch(<DocumentsView />); await screen.findByRole('alert'); failed = false; await userEvent.click(screen.getByRole('button', { name: 'Retry' })); await screen.findByRole('table');
  });
  it('offers an upload action for an empty corpus only when the key has write scope', async () => {
    mockDocuments(async () => list([]), true); mountResearch(<DocumentsView />); await screen.findByText('Your library is empty'); expect(await screen.findByRole('button', { name: 'Upload your first document' })).toBeTruthy();
  });
});

describe('Document upload and polling', () => {
  it('validates locally, then posts the actual file and trimmed metadata and refreshes the library', async () => {
    let posted: FormData | null = null; let lists = 0;
    mockDocuments(async request => { if (request.method === 'POST') { posted = await request.formData(); return Response.json({ job_id: 'job-doc' }); } if (request.url.includes('/jobs/')) return Response.json(ingestionJob); if (request.url.includes('/documents?')) { lists++; return list(); } return detail(); }, true);
    mountResearch(<DocumentsView />); await screen.findByRole('button', { name: 'Upload document' }); fireEvent.click(screen.getByRole('button', { name: 'Upload document' })); fireEvent.click(screen.getByRole('button', { name: 'Start upload' })); expect(screen.getAllByRole('alert').length).toBeGreaterThan(0); expect(posted).toBeNull(); fireEvent.click(screen.getByRole('button', { name: 'Close panel' }));
    await fillUpload(); fireEvent.click(screen.getByRole('button', { name: 'Start upload' })); await screen.findByText('Document ingestion finished'); expect(screen.queryByRole('dialog')).toBeNull(); await waitFor(() => expect(window.document.activeElement).toBe(screen.getByText('Document ingestion finished'))); expect((posted as FormData | null)?.get('title')).toBe('Checks'); expect((posted as FormData | null)?.get('source_agency')).toBe('Agency'); expect((posted as FormData | null)?.get('year')).toBe('2026'); const uploaded = (posted as FormData | null)?.get('file'); expect(uploaded).toBeInstanceOf(File); expect((uploaded as File).name).toBe('checks.md'); await waitFor(() => expect(lists).toBeGreaterThan(1));
  });
  it('rejects multiple dropped files and clears that error when one valid file is chosen', async () => {
    mockDocuments(async request => request.url.includes('/documents?') ? list() : detail(), true);
    mountResearch(<DocumentsView />); await screen.findByRole('button', { name: 'Upload document' }); fireEvent.click(screen.getByRole('button', { name: 'Upload document' }));
    fireEvent.drop(screen.getByText('Drop one document here'), { dataTransfer: { files: [new File(['a'], 'a.md'), new File(['b'], 'b.md')] } });
    expect(screen.getByRole('alert').textContent).toContain('one document at a time');
    fireEvent.change(screen.getByLabelText('Or choose a file'), { target: { files: [new File(['valid'], 'one.md')] } });
    expect(screen.queryByRole('alert')).toBeNull(); expect(screen.getByText(/one.md · 5 bytes selected/)).toBeTruthy();
  });
  it('retains last job status on a polling failure and recovers to a terminal report', async () => {
    let phase: 'running' | 'outage' | 'completed' = 'running';
    mockDocuments(async request => { if (request.method === 'POST') return Response.json({ job_id: 'job-doc' }); if (request.url.includes('/jobs/')) return phase === 'outage' ? Response.json({ error: { code: 'poll_outage', message: 'Polling unavailable' } }, { status: 503 }) : Response.json({ ...ingestionJob, status: phase, report: phase === 'completed' ? ingestionJob.report : null }); return request.url.includes('/documents?') ? list() : detail(); }, true);
    mountResearch(<DocumentsView />); await fillUpload(); vi.useFakeTimers(); fireEvent.click(screen.getByRole('button', { name: 'Start upload' })); await act(async () => {}); expect(screen.getByText('running')).toBeTruthy();
     phase = 'outage'; await act(async () => vi.advanceTimersByTimeAsync(2000)); expect(screen.getByText(/Status updates failed/)).toBeTruthy(); expect(screen.getByText('running')).toBeTruthy(); expect(screen.queryByRole('button', { name: /Cancel/ })).toBeNull();
    phase = 'completed'; await act(async () => vi.advanceTimersByTimeAsync(2000)); expect(screen.getByText('Document ingestion finished')).toBeTruthy(); expect(screen.getByText('Some documents need attention')).toBeTruthy();
  });
});
