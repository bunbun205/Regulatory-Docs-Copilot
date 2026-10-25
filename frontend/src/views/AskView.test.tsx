import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import AskView from './AskView';
import { ask, citation, mockResearch, mountResearch } from '../test/research';

async function submit() { const question = screen.getByLabelText('Your question'); fireEvent.change(question, { target: { value: 'What must staff record?' } }); fireEvent.submit(question.closest('form')!); }
describe('Ask', () => {
  it('opens an actual supplied excerpt with metadata, escapes HTML and restores focus', async () => {
    mockResearch(async () => Response.json({ ...ask, answer: '<img src=x onerror=alert(1)> Record checks [1] [99].', citations: [{ ...citation, snippet: '<script>doSomething()</script> Record checks.' }] }, { headers: { 'X-Request-ID': 'ask-request' } }));
    const { container } = mountResearch(<AskView />); await submit(); await screen.findByText('Citations checked');
    expect(container.querySelector('img,script')).toBeNull(); expect(screen.getAllByText(/\[99\]/).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Citations checked' })); expect(screen.getByText(/This does not prove the source supports/)).toBeTruthy();
    const chip = screen.getByRole('button', { name: 'Source 1: Instrument checks' }); await userEvent.click(chip);
    await screen.findByRole('dialog', { name: 'Source excerpt' }); await screen.findByText('Test agency');
    expect(screen.getByText('<script>doSomething()</script> Record checks.')).toBeTruthy(); expect(screen.getByRole('heading', { name: 'Excerpt' })).toBeTruthy();
    await userEvent.keyboard('{Escape}'); expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(chip);
    await userEvent.click(screen.getByText('Details', { exact: true })); expect(screen.getByText('ask-request')).toBeTruthy(); expect(screen.getByText('20 / 8 / 28')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Open as search/ }).getAttribute('href')).toContain('q=What+must+staff+record');
  });
  it('provides numbered sources without inventing inline citation placement', async () => {
    mockResearch(async () => Response.json({ ...ask, answer: 'A plain answer with no markers.' })); mountResearch(<AskView />); await submit(); await screen.findByText('A plain answer with no markers.');
    expect(screen.queryByRole('button', { name: 'Source 1: Instrument checks' })).toBeNull(); expect(screen.getByRole('button', { name: 'Read source 1: Instrument checks' })).toBeTruthy();
  });
  it('shows abstention and best relevance without displaying citations', async () => {
    mockResearch(async () => Response.json({ ...ask, insufficient_evidence: true, answer: 'Not enough evidence in the loaded documents.', grounded: false, top_score: 0.12 })); mountResearch(<AskView />); await submit();
    await screen.findByText('Not enough evidence', { exact: true }); expect(screen.getByText('0.120')).toBeTruthy(); expect(screen.queryByRole('button', { name: /Read source/ })).toBeNull(); expect(screen.queryByText('Citations checked')).toBeNull();
  });
  it('shows an ungrounded status before the answer', async () => {
    mockResearch(async () => Response.json({ ...ask, grounded: false, grounding_reason: 'no_valid_citations' })); mountResearch(<AskView />); await submit();
    await screen.findByText('Sources need review'); const warning = screen.getByText('Sources need review'); const answer = screen.getByRole('heading', { name: 'Answer' }); expect(warning.compareDocumentPosition(answer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it('prevents duplicate requests and discards a stopped answer and its history', async () => {
    let finish!: (response: Response) => void; let signal: AbortSignal | null = null;
    const fetcher = mockResearch(async (_request, init) => { signal = init?.signal ?? null; return new Promise<Response>(resolve => { finish = resolve; }); });
    mountResearch(<AskView />); await submit(); await waitFor(() => expect(finish).toBeDefined()); fireEvent.submit(screen.getByLabelText('Your question').closest('form')!);
    expect(fetcher.mock.calls.filter(([request]) => request.url.endsWith('/ask'))).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: 'Stop waiting' })); expect((signal as AbortSignal | null)?.aborted).toBe(true);
    await act(async () => finish(Response.json(ask))); expect(screen.queryByText('Citations checked')).toBeNull(); expect(screen.queryByText(/Session history/)).toBeNull(); expect(screen.queryByRole('alert')).toBeNull();
  });
  it('shows a retryable failure and stores successful Q&A only in this session', async () => {
    let attempts = 0; mockResearch(async () => ++attempts === 1 ? Response.json({ error: { code: 'llm_error', message: 'Fixture outage', request_id: 'ask-error' } }, { status: 502 }) : Response.json(ask));
    mountResearch(<AskView />); await submit(); await screen.findByRole('alert'); expect(screen.queryByText('Citations checked')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' })); await screen.findByText('Citations checked');
    await userEvent.click(screen.getByText('Session history (1/10)')); expect(sessionStorage.getItem('docs_copilot_ask_history')).toContain(citation.snippet); expect(JSON.stringify(localStorage)).not.toContain(citation.snippet);
    await userEvent.click(screen.getByRole('button', { name: 'Clear history' })); expect(screen.queryByText('Session history (1/10)')).toBeNull(); expect(screen.getByText('Citations checked')).toBeTruthy();
  });
});
