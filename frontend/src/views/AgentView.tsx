import { useState } from 'react';
import { useSettings } from '../app/context';
import { useAsync } from '../hooks/useAsync';
import type { components } from '../types/api';
import { Banner, EmptyState } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';

export default function AgentView() {
  const { api, preferences } = useSettings();
  const [query, setQuery] = useState('');
  const action = useAsync<components['schemas']['AgentResponse']>();
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    void action.run(signal => api.request(() => api.client.POST('/v1/agent/run', { signal, body: { query: query.trim(), backend: preferences.backend } })));
  };
  const result = action.data;
  return <div><form onSubmit={submit}><label htmlFor="agent-query">Research question</label><input id="agent-query" type="text" value={query} onChange={event => setQuery(event.target.value)} placeholder="Explore a question across your documents" disabled={action.pending} /><button type="submit" disabled={action.pending || action.retryIn > 0 || !query.trim()}>Run agent</button></form><RequestStatus action={action} baseUrl={preferences.baseUrl} />
    {!result && !action.pending && !action.error && <EmptyState title="Follow the research">The agent can search documents and compare their metadata, within a five-step limit.</EmptyState>}
    {result && <div style={{ display: 'grid', gap: 24, marginTop: 24 }}>
      {result.partial && <Banner tone="warning" title="This run is incomplete">The agent stopped before finishing. Review the answer and trace. {result.partial_reason && <span>Reason: {result.partial_reason}.</span>}</Banner>}
      {!result.grounded && <Banner tone="warning">This answer does not have checked source citations. Review it carefully.</Banner>}
      <section><h2>Answer</h2><p>{result.answer}</p>{result.citations.map(citation => <div key={citation.chunk_id} className="citation">{citation.title}{citation.page !== null && ` · Page ${citation.page}`}</div>)}</section>
      <section><h2>Execution trace</h2>{result.trace.length === 0 && <p>No tool steps were completed.</p>}{result.trace.map(step => <div key={step.step} className="trace-step"><strong>Step {step.step}: {step.tool}</strong><pre>{JSON.stringify(step.arguments, null, 2)}</pre><p>{step.result_summary} · {step.latency_ms} ms</p></div>)}</section>
    </div>}
  </div>;
}
