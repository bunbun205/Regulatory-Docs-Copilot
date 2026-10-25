import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useSettings } from '../app/context';
import { useAsync } from '../hooks/useAsync';
import type { components } from '../types/api';
import { apiFilters, emptyFilters, filterError, overlap, runResult, validTopK } from '../domain/research';
import type { Backend, Run } from '../domain/research';
import { Badge, Button, Card, Disclosure, EmptyState, Field, Input, Skeleton } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';
import ResearchControls from '../components/research/ResearchControls';
import { SourceCard } from '../components/research/Sources';
import styles from '../components/research/research.module.css';

type SearchRun = Run<components['schemas']['SearchResponse']>;
export default function SearchView() {
  const { api, preferences } = useSettings(); const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get('q')?.slice(0, 2000) ?? ''); const [filters, setFilters] = useState(emptyFilters);
  const [backend, setBackend] = useState<Backend>(preferences.backend); const [topK, setTopK] = useState(String(preferences.topK));
  const [compare, setCompare] = useState(false); const [submitted, setSubmitted] = useState<{ query: string; compare: boolean } | null>(null);
  const primary = useAsync<SearchRun>(); const secondary = useAsync<SearchRun>();
  const pending = primary.pending || secondary.pending;
  const submit = (event: React.FormEvent) => {
    event.preventDefault(); if (!query.trim() || !validTopK(topK) || filterError(filters) || pending) return;
    const body = { query: query.trim(), top_k: Number(topK), ...(apiFilters(filters) && { filters: apiFilters(filters) }) };
    setSubmitted({ query: body.query, compare }); secondary.clear();
    const request = (selected: Backend) => async (signal: AbortSignal) => runResult(await api.request(() => api.client.POST('/v1/search', { signal, body: { ...body, backend: selected } })));
    void primary.run(request(compare ? 'pgvector' : backend));
    if (compare) void secondary.run(request('qdrant'));
  };
  const shared = primary.data && secondary.data ? overlap(primary.data.payload.results, secondary.data.payload.results) : null;
  const column = (action: typeof primary, label: string) => <div className={styles.column}>{submitted?.compare && <h2>{label}</h2>}<RequestStatus action={action} baseUrl={preferences.baseUrl} />{action.pending && <Card><Skeleton lines={6} /></Card>}{action.data && <><p className={styles.hint}>{action.data.payload.results.length} passages · {action.data.payload.latency_ms?.toFixed(1) ?? '—'} ms</p>{action.data.payload.results.length === 0 && <EmptyState title="No passages found">Try a different query or adjust the document filters.</EmptyState>}{action.data.payload.results.map(hit => <SourceCard key={hit.chunk_id} hit={hit} />)}<Disclosure title="Request details"><dl className={styles.details}><dt>Request ID</dt><dd>{action.data.requestId ?? 'Unavailable'}</dd><dt>Backend</dt><dd>{action.data.payload.backend}</dd></dl></Disclosure></>}</div>;
  return <div className={styles.stack}><Card><form className={styles.form} onSubmit={submit}><Field id="search-query" label="Search your library"><Input id="search-query" type="text" value={query} maxLength={2000} onChange={event => setQuery(event.target.value)} placeholder="A topic, requirement or phrase" disabled={pending} /></Field><ResearchControls filters={filters} setFilters={setFilters} backend={backend} setBackend={setBackend} topK={topK} setTopK={setTopK} disabled={pending} advanced={false} /><label className={styles.check}><input type="checkbox" checked={compare} disabled={pending} onChange={event => setCompare(event.target.checked)} />Compare backends</label>{compare && <p className={styles.hint}>Run the same query, filters and source count against pgvector and Qdrant. Results and failures appear independently.</p>}<div><Button type="submit" disabled={pending || primary.retryIn > 0 || secondary.retryIn > 0 || !query.trim() || !validTopK(topK) || Boolean(filterError(filters))}><Search size={16} aria-hidden="true" />Search</Button></div></form></Card>
    {!submitted && <EmptyState title="Find a passage">Search returns relevant source passages from your loaded documents. Relevance scores are not confidence estimates.</EmptyState>}
    {submitted && <><div className={styles.resultHeader}><h2>Results</h2>{submitted.compare && shared && <Badge>{shared.shared} of {shared.total} shared</Badge>}</div><p className={styles.hint}>For “{submitted.query}”{submitted.compare && ' · Overlap counts shared chunk IDs out of all unique returned chunks.'}</p><div className={submitted.compare ? styles.compare : styles.column}>{column(primary, 'pgvector')}{submitted.compare && column(secondary, 'Qdrant')}</div></>}
  </div>;
}
