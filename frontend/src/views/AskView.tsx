import { useState } from 'react';
import { useSettings } from '../app/context';
import { useAsync } from '../hooks/useAsync';
import type { components } from '../types/api';
import { EmptyState } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';

export default function AskView() {
  const { api, preferences } = useSettings();
  const [question, setQuestion] = useState('');
  const action = useAsync<components['schemas']['AskResponse']>();
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    void action.run(signal => api.request(() => api.client.POST('/v1/ask', { signal, body: { query: question.trim(), top_k: preferences.topK, backend: preferences.backend } })));
  };
  return <div>
    <form onSubmit={submit}><label htmlFor="ask-question">Your question</label><textarea id="ask-question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="What do the loaded regulations say about…" disabled={action.pending} /><button type="submit" disabled={action.pending || action.retryIn > 0 || !question.trim()}>Ask documents</button></form>
    <RequestStatus action={action} baseUrl={preferences.baseUrl} />
    {!action.data && !action.pending && !action.error && !action.stopped && <EmptyState title="Start with a question">Ask about a procedure, a requirement or a point that needs a closer look. Review the sources alongside each answer.</EmptyState>}
    {action.data && <section aria-label="Answer"><h2>Answer</h2><p>{action.data.answer}</p><h3>Sources</h3>{action.data.citations.map(citation => <div key={citation.chunk_id} className="citation"><strong>{citation.title}</strong>{citation.page !== null && <span> · Page {citation.page}</span>}<p>{citation.snippet}</p></div>)}</section>}
  </div>;
}
