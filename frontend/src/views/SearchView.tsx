import { useState } from 'react';
import { useSettings } from '../app/context';
import { useAsync } from '../hooks/useAsync';
import type { components } from '../types/api';
import { EmptyState } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';

export default function SearchView() {
  const { api, preferences } = useSettings();
  const [query, setQuery] = useState('');
  const action = useAsync<components['schemas']['SearchResponse']>();
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    void action.run(signal => api.request(() => api.client.POST('/v1/search', { signal, body: { query: query.trim(), top_k: preferences.topK, backend: preferences.backend } })));
  };
  return <div><form onSubmit={submit}><label htmlFor="search-query">Search your library</label><input id="search-query" type="text" value={query} onChange={event => setQuery(event.target.value)} placeholder="A topic, requirement or phrase" disabled={action.pending} /><button type="submit" disabled={action.pending || action.retryIn > 0 || !query.trim()}>Search</button></form><RequestStatus action={action} baseUrl={preferences.baseUrl} />
    {!action.data && !action.pending && !action.error && <EmptyState title="Find a passage">Search returns relevant source passages from your loaded documents.</EmptyState>}
    {action.data?.results.length === 0 && <EmptyState title="No passages found">Try a different query or check which documents are loaded.</EmptyState>}
    {action.data?.results.map(hit => <div key={hit.chunk_id} className="citation"><strong>{hit.title}</strong> · Score {hit.score.toFixed(4)}<pre>{hit.text}</pre></div>)}
  </div>;
}
