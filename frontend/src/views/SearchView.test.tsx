import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import SearchView from './SearchView';
import { hit, mockResearch, mountResearch } from '../test/research';

function submit() { fireEvent.submit(screen.getByLabelText('Search your library').closest('form')!); }
describe('Search', () => {
  it('prefills deep links, renders empty results and does not submit automatically', async () => {
    const fetcher = mockResearch(async () => Response.json({ results: [], backend: 'pgvector', latency_ms: 3 })); mountResearch(<SearchView />, '/search?q=instrument+checks');
    expect((screen.getByLabelText('Search your library') as HTMLInputElement).value).toBe('instrument checks'); expect(screen.getByText('Find a passage')).toBeTruthy();
    expect(fetcher.mock.calls.filter(([request]) => request.url.endsWith('/search'))).toHaveLength(0); submit(); await screen.findByText('No passages found');
  });
  it('compares the same parameters and shows independent results and unique overlap', async () => {
    const bodies: Record<string, unknown>[] = [];
    mockResearch(async request => { const body = await request.json(); bodies.push(body); return Response.json({ query: body.query, backend: body.backend, results: [hit, { ...hit, chunk_id: body.backend, title: String(body.backend) + ' extra' }], latency_ms: 2 }); });
    const { container } = mountResearch(<SearchView />); fireEvent.change(screen.getByLabelText('Search your library'), { target: { value: 'records' } });
    await userEvent.click(screen.getByRole('button', { name: 'Filters' })); fireEvent.change(screen.getByLabelText('Agency'), { target: { value: 'FDA' } }); fireEvent.change(screen.getByLabelText('Start year'), { target: { value: '2020' } }); await userEvent.click(screen.getByRole('button', { name: 'Done' }));
    await userEvent.click(screen.getByLabelText('Compare backends')); submit(); await screen.findByText('1 of 3 shared');
    expect(bodies).toHaveLength(2); expect(bodies.map(body => body.backend).sort()).toEqual(['pgvector', 'qdrant']); expect(bodies.every(body => JSON.stringify(body.filters) === JSON.stringify({ source_agency: 'FDA', year_min: 2020 }))).toBe(true);
    expect(screen.getAllByRole('heading', { name: 'Excerpt' })).toHaveLength(4); expect(container.querySelector('script')).toBeNull();
  });
  it('keeps a successful backend visible when its comparison partner fails', async () => {
    mockResearch(async request => (await request.json()).backend === 'qdrant' ? Response.json({ error: { code: 'unavailable', message: 'Qdrant fixture outage' } }, { status: 503 }) : Response.json({ query: 'checks', backend: 'pgvector', results: [hit], latency_ms: 2 }));
    mountResearch(<SearchView />, '/search?q=checks'); await userEvent.click(screen.getByLabelText('Compare backends')); submit(); await screen.findByRole('alert'); expect(await screen.findByRole('heading', { name: /Instrument checks/ })).toBeTruthy(); expect(screen.queryByText(/of .* shared/)).toBeNull();
  });
  it('prevalidates inverted year filters without issuing a search', async () => {
    const fetcher = mockResearch(async () => Response.json({})); mountResearch(<SearchView />, '/search?q=checks');
    await userEvent.click(screen.getByRole('button', { name: 'Filters' })); fireEvent.change(screen.getByLabelText('Start year'), { target: { value: '2026' } }); fireEvent.change(screen.getByLabelText('End year'), { target: { value: '2020' } }); submit();
    expect(screen.getAllByText('Start year must be no later than end year.').length).toBeGreaterThan(0); expect(fetcher.mock.calls.filter(([request]) => request.url.endsWith('/search'))).toHaveLength(0);
  });
  it('stops waiting without accepting a late result', async () => {
    let finish!: (response: Response) => void; mockResearch(async () => new Promise(resolve => { finish = resolve; }));
    mountResearch(<SearchView />, '/search?q=checks'); submit(); await waitFor(() => expect(finish).toBeDefined());
    expect(screen.getByRole('button', { name: 'Search' }).hasAttribute('disabled')).toBe(true); await userEvent.click(screen.getByRole('button', { name: 'Stop waiting' }));
    await act(async () => finish(Response.json({ results: [hit], backend: 'pgvector', latency_ms: 2 }))); expect(screen.queryByRole('heading', { name: /Instrument checks/ })).toBeNull(); expect(screen.getByText(/The server may keep working/)).toBeTruthy();
  });
});
