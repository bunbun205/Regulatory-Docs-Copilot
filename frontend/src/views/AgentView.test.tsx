import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import AgentView from './AgentView';
import type { components } from '../types/api';
import { ask, mockResearch, mountResearch } from '../test/research';
const agent: components['schemas']['AgentResponse'] = { query: 'checks', backend: 'pgvector', answer: ask.answer, citations: ask.citations, grounded: true, grounding_reason: null, trace: [{ step: 1, tool: 'search_documents', arguments: { query: '<script>untrusted</script>' }, result_summary: 'Returned one chunk; output truncated', latency_ms: 20, error: null }], step_count: 1, partial: false, partial_reason: null, usage: ask.usage, latency_ms: 100 };
function submit() { const input = screen.getByLabelText('Research question'); fireEvent.change(input, { target: { value: 'checks' } }); fireEvent.submit(input.closest('form')!); }
describe('Agent status and trace', () => {
  it.each([['timeout', 'Stopped at the time limit'], ['step_limit', 'Stopped at the tool-step limit'], ['other_limit', 'The agent stopped before finishing']])('places partial %s and ungrounded status before an empty answer', async (reason, explanation) => {
    mockResearch(async () => Response.json({ ...agent, answer: '', citations: [], grounded: false, partial: true, partial_reason: reason, trace: [], step_count: 0 }));
    mountResearch(<AgentView />); submit(); await screen.findByText('This run is incomplete'); expect(screen.getByText(new RegExp(explanation))).toBeTruthy();
    const answer = screen.getByRole('heading', { name: 'Answer' }); for (const label of ['This run is incomplete', 'Sources need review']) expect(screen.getByText(label).compareDocumentPosition(answer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('No tool steps were completed.')).toBeTruthy(); expect(screen.getByText(/No answer text was returned/)).toBeTruthy(); expect(screen.queryByText('Citations checked')).toBeNull();
  });
  it('renders safe collapsible arguments, actual truncation markers, latency and tool errors', async () => {
    mockResearch(async () => Response.json({ ...agent, trace: [{ ...agent.trace[0], error: '<img src=x onerror=alert(1)>' }] }));
    const { container } = mountResearch(<AgentView />); submit(); await screen.findByText('Execution trace');
    await userEvent.click(screen.getByText('View tool steps (1)')); await userEvent.click(screen.getByText('Arguments for step 1'));
    expect(screen.getByText('Output truncated')).toBeTruthy(); expect(screen.getByText('20.0 ms')).toBeTruthy(); expect(screen.getByText('Tool step failed')).toBeTruthy();
    expect(screen.getByText(/"query": "<script>untrusted<\/script>"/)).toBeTruthy(); expect(container.querySelector('script,img')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Source 1: Instrument checks' })); expect(await screen.findByRole('dialog', { name: 'Source excerpt' })).toBeTruthy();
  });
  it('does not infer truncation when the API summary has no marker', async () => {
    mockResearch(async () => Response.json({ ...agent, trace: [{ ...agent.trace[0], result_summary: 'Returned one chunk.' }] })); mountResearch(<AgentView />); submit(); await screen.findByText('Execution trace'); expect(screen.queryByText('Output truncated')).toBeNull();
  });
  it('keeps unknown partial reasons as text in Details', async () => {
    const reason = '<img src=x onerror=alert(1)>'; mockResearch(async () => Response.json({ ...agent, partial: true, partial_reason: reason }));
    const { container } = mountResearch(<AgentView />); submit(); await screen.findByText('This run is incomplete'); await userEvent.click(screen.getByText('Details', { exact: true })); expect(screen.getByText(reason)).toBeTruthy(); expect(container.querySelector('img')).toBeNull();
  });
  it('prevents duplicates, stops waiting and ignores a late successful run', async () => {
    let finish!: (response: Response) => void; const fetcher = mockResearch(async () => new Promise(resolve => { finish = resolve; }));
    mountResearch(<AgentView />); expect(screen.getByText('Follow the research')).toBeTruthy(); submit(); await waitFor(() => expect(finish).toBeDefined()); fireEvent.submit(screen.getByLabelText('Research question').closest('form')!);
    expect(fetcher.mock.calls.filter(([request]) => request.url.endsWith('/agent/run'))).toHaveLength(1); await userEvent.click(screen.getByRole('button', { name: 'Stop waiting' })); await act(async () => finish(Response.json(agent)));
    expect(screen.queryByText('Execution trace')).toBeNull(); expect(screen.getByText(/The server may keep working/)).toBeTruthy(); expect(screen.queryByRole('alert')).toBeNull();
  });
  it('exposes a failed run through the shared retry and copy-details UI', async () => {
    mockResearch(async () => Response.json({ error: { code: 'llm_unavailable', message: 'Fixture timeout', request_id: 'agent-error' } }, { status: 502 })); mountResearch(<AgentView />); submit(); await screen.findByRole('alert'); expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy(); expect(screen.getByRole('button', { name: 'Copy details' })).toBeTruthy(); expect(screen.queryByText('Execution trace')).toBeNull();
  });
});
