import { useState } from 'react';
import { Sparkles, TriangleAlert } from 'lucide-react';
import { useSettings } from '../app/context';
import { useAsync } from '../hooks/useAsync';
import type { components } from '../types/api';
import { apiFilters, emptyFilters, filterError, runResult } from '../domain/research';
import type { Backend, Run } from '../domain/research';
import { partialExplanation, toolName } from '../domain/agent';
import { Badge, Banner, Button, Card, Disclosure, EmptyState, Field, Select, Skeleton } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';
import { FilterBar } from '../components/research/ResearchControls';
import { AnswerPanel, RunDetails } from '../components/research/Sources';
import styles from '../components/research/research.module.css';
import traceStyles from './AgentView.module.css';

export default function AgentView() {
  const { api, preferences } = useSettings(); const [query, setQuery] = useState('');
  const [backend, setBackend] = useState<Backend>(preferences.backend); const [filters, setFilters] = useState(emptyFilters);
  const action = useAsync<Run<components['schemas']['AgentResponse']>>();
  const submit = (event: React.FormEvent) => {
    event.preventDefault(); if (!query.trim() || filterError(filters)) return;
    void action.run(async signal => runResult(await api.request(() => api.client.POST('/v1/agent/run', { signal, body: { query: query.trim(), backend, ...(apiFilters(filters) && { filters: apiFilters(filters) }) } }))));
  };
  const result = action.data?.payload;
  return <div className={styles.stack}><Card><form className={styles.form} onSubmit={submit}><Field id="agent-query" label="Research question" hint="The agent chooses document-search and metadata tools within a bounded run."><textarea id="agent-query" className={styles.question} aria-describedby="agent-query-hint" value={query} onChange={event => setQuery(event.target.value)} placeholder="Explore a question across your documents" maxLength={2000} disabled={action.pending} /></Field><fieldset className={styles.controls} disabled={action.pending}><div className={styles.grid}><FilterBar values={filters} onChange={setFilters} /><Field id="agent-backend" label="Vector backend"><Select id="agent-backend" value={backend} onChange={event => setBackend(event.target.value as Backend)}><option value="pgvector">pgvector</option><option value="qdrant">Qdrant</option></Select></Field></div>{filterError(filters) && <p role="alert" className={styles.error}>{filterError(filters)}</p>}</fieldset><div className={styles.actions}><Button type="submit" disabled={action.pending || action.retryIn > 0 || !query.trim() || Boolean(filterError(filters))}><Sparkles size={16} aria-hidden="true" />Run agent</Button><span className={styles.hint}>A local model can take up to 3 minutes.</span></div></form><RequestStatus action={action} baseUrl={preferences.baseUrl} /></Card>
    {!result && !action.pending && !action.error && !action.stopped && <EmptyState title="Follow the research">See which tools the agent used, what they returned, and where its answer needs review.</EmptyState>}
    {action.pending && <Card><Skeleton lines={5} /></Card>}
    {result && <>{result.partial && <Banner tone="warning" title="This run is incomplete"><p>{partialExplanation(result.partial_reason)}</p></Banner>}
      <AnswerPanel answer={result.answer} citations={result.citations} grounded={result.grounded} details={<><RunDetails backend={result.backend} usage={result.usage} latency={result.latency_ms} requestId={action.data?.requestId ?? null} reason={result.grounding_reason} /><dl className={styles.details} style={{ marginTop: 12 }}><dt>Partial run</dt><dd>{result.partial ? 'Yes' : 'No'}</dd><dt>Partial reason</dt><dd>{result.partial_reason ?? 'None supplied'}</dd><dt>Tool steps</dt><dd>{result.step_count}</dd></dl></>} />
      <Card><h2 className={styles.heading}>Execution trace</h2><p className={styles.hint}>{result.step_count} tool {result.step_count === 1 ? 'step' : 'steps'} reported. Tool output is evidence to review.</p>{result.trace.length === 0 ? <p>No tool steps were completed.</p> : <Disclosure title={`View tool steps (${result.trace.length})`}><ol className={traceStyles.timeline}>{result.trace.map((step, index) => <li className={traceStyles.step} key={`${step.step}:${index}`}><div className={traceStyles.header}><Badge>Step {step.step}</Badge><h3>{toolName(step.tool)}</h3><small>{step.latency_ms.toFixed(1)} ms</small></div><p className={traceStyles.summary}>{step.result_summary}</p>{step.result_summary.includes('; output truncated') && <Badge tone="warning"><TriangleAlert size={12} aria-hidden="true" />Output truncated</Badge>}{step.error && <Banner tone="danger" title="Tool step failed"><p>{step.error}</p></Banner>}<Disclosure title={`Arguments for step ${step.step}`}><pre className={traceStyles.code}>{JSON.stringify(step.arguments, null, 2)}</pre></Disclosure></li>)}</ol></Disclosure>}</Card></>}
  </div>;
}
