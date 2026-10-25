import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Files, ShieldCheck } from 'lucide-react';
import { useSettings } from '../../app/context';
import { multipart } from '../../api/contracts';
import { useAsync } from '../../hooks/useAsync';
import { usePolling } from '../../hooks/usePolling';
import type { components } from '../../types/api';
import { apiFilters, emptyFilters, filterError } from '../../domain/research';
import type { Backend } from '../../domain/research';
import { DEFAULT_SOP_CHARS, fileError } from '../../domain/gap';
import { Banner, Button, Card, Disclosure, ErrorBanner, Field, Select, Tabs } from '../ui';
import RequestStatus from '../ui/RequestStatus';
import { FilterBar } from '../research/ResearchControls';
import research from '../research/research.module.css';
import styles from './gap.module.css';

const once = () => true;
export default function GapInput() {
  const { api, preferences } = useSettings(); const navigate = useNavigate();
  const [mode, setMode] = useState('text'); const [text, setText] = useState(''); const [file, setFile] = useState<File | null>(null);
  const [filters, setFilters] = useState(emptyFilters); const [debounced, setDebounced] = useState(emptyFilters);
  const [backend, setBackend] = useState<Backend>(preferences.backend); const [validation, setValidation] = useState('');
  useEffect(() => { const timer = setTimeout(() => setDebounced(filters), 300); return () => clearTimeout(timer); }, [filters]);
  const loadScope = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/documents', { signal, params: { query: { ...apiFilters(debounced), limit: 3 } } })), [api, debounced]);
  const scope = usePolling(loadScope, !filterError(debounced), 2000, once);
  const scopePending = scope.pending || JSON.stringify(filters) !== JSON.stringify(debounced);
  const action = useAsync<components['schemas']['GapCheckSubmitResponse']>();
  const inputError = mode === 'file' ? fileError(file) : !text.trim() ? 'Paste the SOP text to review.' : text.length > DEFAULT_SOP_CHARS ? 'The SOP exceeds the 200,000-character local precheck limit.' : undefined;
  const submit = (event: React.FormEvent) => {
    event.preventDefault(); if (inputError || filterError(filters)) { setValidation(inputError ?? filterError(filters) ?? 'Check the input.'); return; }
    setValidation('');
    const values = { ...(mode === 'file' ? { file: '' } : { text: text.trim() }), backend, ...apiFilters(filters) };
    void action.run(async signal => {
      const result = await api.request(() => api.client.POST('/v1/gapcheck', { signal, body: values, bodySerializer: body => multipart(body ?? {}, mode === 'file' ? file : null) }));
      if (result.ok && !signal.aborted) navigate(`/gap-check/${result.data.job_id}`);
      return result;
    });
  };
  const selectedFileError = mode === 'file' && file ? fileError(file) : undefined;
  return <div className={styles.stack}><Card><div className={styles.intro}><div className={styles.mark}><ShieldCheck size={24} aria-hidden="true" /></div><div><h2 className={styles.title}>A second look at your SOP</h2><p className={styles.lead}>Compare a procedure with the regulations in your library, in both directions. Review conflicts and requirements the SOP may have missed.</p></div></div></Card><Card><form className={styles.form} onSubmit={submit}><Tabs label="SOP input" items={[{ value: 'text', label: 'Paste text' }, { value: 'file', label: 'Upload file' }]} selected={mode} onChange={value => { if (!action.pending) { setMode(value); setValidation(''); } }} />
    {mode === 'text' ? <Field id="sop-text" label="SOP text" hint={`${text.length.toLocaleString()} / ${DEFAULT_SOP_CHARS.toLocaleString()} characters · paste headings and procedure text.`}><textarea id="sop-text" aria-describedby="sop-text-hint" className={research.question} style={{ minHeight: 240 }} value={text} maxLength={DEFAULT_SOP_CHARS} onChange={event => { setText(event.target.value); setValidation(''); }} placeholder="Paste the SOP you want to review…" disabled={action.pending} /></Field> : <div className={styles.file}><Field id="sop-file" label="SOP file" hint="PDF, Markdown (.md) or text (.txt). Local precheck: up to 25 MiB. The server may apply a smaller limit." error={selectedFileError}><input id="sop-file" type="file" accept=".pdf,.md,.txt" aria-describedby="sop-file-hint" aria-invalid={Boolean(selectedFileError)} disabled={action.pending} onChange={event => { setFile(event.target.files?.[0] ?? null); setValidation(''); }} /></Field>{file && <p className={research.hint} style={{ marginTop: 12 }}>{file.name} · {(file.size / 1024).toFixed(1)} KiB</p>}</div>}
    <fieldset className={research.controls} disabled={action.pending}><div className={research.grid}><div><h3 className={research.subheading}>Regulation scope</h3><FilterBar values={filters} onChange={setFilters} /></div><Field id="gap-backend" label="Vector backend"><Select id="gap-backend" value={backend} onChange={event => setBackend(event.target.value as Backend)}><option value="pgvector">pgvector</option><option value="qdrant">Qdrant</option></Select></Field></div>{filterError(filters) && <p role="alert" className={research.error}>{filterError(filters)}</p>}</fieldset>
    <div>{scopePending ? <p role="status" className={styles.scope}>Checking document scope…</p> : scope.data && !scope.error && !filterError(filters) && <><p role="status" className={styles.scope}><Files size={16} aria-hidden="true" />{scope.data.total} {scope.data.total === 1 ? 'document matches' : 'documents match'} these filters.</p><p className={research.hint}>The run checks retrieved requirements within this scope.</p><Disclosure title="Documents in scope">{scope.data.items.map(document => <p key={document.id}>{document.title} · {document.source_agency} · {document.year}</p>)}{scope.data.total > 3 && <p>And {scope.data.total - 3} more matching documents.</p>}</Disclosure></>}{scope.error && <ErrorBanner error={scope.error} baseUrl={preferences.baseUrl} onRetry={scope.refresh} />}</div>
    {validation && <p role="alert" className={research.error}>{validation}</p>}<div className={research.actions}><Button type="submit" disabled={action.pending || action.retryIn > 0 || Boolean(inputError) || Boolean(filterError(filters))}><ShieldCheck size={16} aria-hidden="true" />Run gap check</Button><p className={research.hint}>Local analysis can take several minutes. You can return to the run’s URL.</p></div></form><RequestStatus action={action} baseUrl={preferences.baseUrl} canStop={false} /></Card><Banner tone="info" title="For your review">Findings support your review. They do not establish compliance, and the analysis is limited to the loaded documents.</Banner></div>;
}
