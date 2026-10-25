import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, FileText, RefreshCw, Upload, X } from 'lucide-react';
import { useSettings } from '../app/context';
import { usePolling } from '../hooks/usePolling';
import useDocumentChunks from '../hooks/useDocumentChunks';
import { apiFilters, emptyFilters, filterError } from '../domain/research';
import type { FilterValues } from '../domain/research';
import { ingestionTerminal, pageDocuments } from '../domain/documents';
import type { Document, DocumentSort } from '../domain/documents';
import { Badge, Banner, Button, Card, Disclosure, ElapsedTimer, EmptyState, ErrorBanner, Field, Input, Select, Skeleton, Spinner } from '../components/ui';
import IngestionReport from '../components/documents/IngestionReport';
import UploadDrawer from '../components/documents/UploadDrawer';
import styles from '../components/documents/documents.module.css';

const noDocuments: Document[] = [];
const filterFields = [['agency', 'Agency', 200], ['type', 'Document type', 100], ['yearMin', 'Start year', 4], ['yearMax', 'End year', 4]] as const;
export default function DocumentsView() {
  const { api, identity, preferences } = useSettings();
  const [filters, setFilters] = useState<FilterValues>(emptyFilters); const [draft, setDraft] = useState<FilterValues>(emptyFilters);
  const [offset, setOffset] = useState(0); const [limit, setLimit] = useState(10); const [query, setQuery] = useState(''); const [sort, setSort] = useState<DocumentSort>('newest');
  const [open, setOpen] = useState(false); const [jobId, setJobId] = useState<string | null>(null); const [revision, setRevision] = useState(0); const completed = useRef<string | null>(null); const jobHeading = useRef<HTMLHeadingElement>(null);
  const loadDocuments = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/documents', { params: { query: { ...apiFilters(filters), limit, offset } }, signal })), [api, filters, limit, offset]);
  const documents = usePolling(loadDocuments, true, 60_000);
  const refreshDocuments = documents.refresh;
  const loadJob = useCallback(async (signal: AbortSignal) => {
    const result = await api.request(() => api.client.GET('/v1/jobs/{job_id}', { params: { path: { job_id: jobId ?? '' } }, signal }));
    if (!signal.aborted && result.ok && ingestionTerminal(result.data) && completed.current !== result.data.id) { completed.current = result.data.id; setRevision(value => value + 1); refreshDocuments(); }
    return result;
  }, [api, jobId, refreshDocuments]);
  const job = usePolling(loadJob, Boolean(jobId), 2000, ingestionTerminal);
  const running = Boolean(jobId) && (!job.data || !ingestionTerminal(job.data));
  const canWrite = identity?.scopes.includes('write') ?? false;
  const rows = useMemo(() => pageDocuments(documents.data?.items ?? noDocuments, query, sort), [documents.data, query, sort]);
  const chunks = useDocumentChunks(rows, revision);
  const total = documents.data?.total ?? 0; const loaded = documents.data?.items.length ?? 0;
  useEffect(() => { if (jobId) jobHeading.current?.focus(); }, [jobId]);
  const accepted = useCallback((id: string) => setJobId(id), []);
  const close = useCallback(() => setOpen(false), []);
  function apply(values: FilterValues) { setFilters(values); setDraft(values); setOffset(0); }
  const hasFilters = Object.keys(apiFilters(filters) ?? {}).length > 0;
  const refresh = () => { setRevision(value => value + 1); documents.refresh(); };
  return <div className={styles.stack}>
    <div className={styles.toolbar}><div><h2 className={styles.heading}>Document library</h2><p className={styles.hint}>The sources your workspace can search and cite.</p></div><div className={styles.actions}><Button variant="secondary" onClick={refresh}><RefreshCw size={15} aria-hidden="true" />Refresh</Button>{canWrite && <Button onClick={() => setOpen(true)} disabled={running}><Upload size={16} aria-hidden="true" />Upload document</Button>}</div></div>
    {!canWrite && <Banner title="Uploads need write access">{identity ? 'This key is read only. You can still browse the document library.' : 'Validate your key in Settings to check upload access.'}</Banner>}
    {jobId && <Card><div className={styles.stack}><div className={styles.toolbar}><div className={styles.actions}>{running ? <Spinner /> : <FileText size={18} aria-hidden="true" />}<h2 ref={jobHeading} tabIndex={-1} className={styles.heading}>{running ? 'Ingesting your document' : job.data?.status === 'failed' ? 'Document ingestion failed' : 'Document ingestion finished'}</h2><Badge tone={job.data?.status === 'failed' ? 'danger' : running ? 'info' : 'neutral'}>{job.data?.status ?? 'Waiting for status'}</Badge></div>{running && job.data?.started_at && <ElapsedTimer startedAt={Date.parse(job.data.started_at)} />}</div><p className={styles.hint}>Run {jobId}</p>{running && <p role="status" className={styles.text}>Status updates every 2 seconds. You can browse the library while the server works.</p>}{job.error && <><Banner tone="warning">Status updates failed. The server may still be working; the last confirmed state is shown.</Banner><ErrorBanner error={job.error} baseUrl={preferences.baseUrl} onRetry={job.refresh} /></>}{job.data && ingestionTerminal(job.data) && <IngestionReport job={job.data} />}</div></Card>}
    <Card><div className={styles.stack}><div className={styles.toolbar}><div className={styles.search}><Field id="document-search" label="Search titles on this page"><Input id="document-search" type="search" maxLength={500} placeholder="Find a title on the loaded page" value={query} onChange={event => setQuery(event.target.value)} /></Field></div><div className={styles.sort}><Field id="document-sort" label="Sort this page"><Select id="document-sort" value={sort} onChange={event => setSort(event.target.value as DocumentSort)}><option value="newest">Server order (newest first)</option><option value="title">Title A–Z</option><option value="title-desc">Title Z–A</option><option value="year-desc">Year, newest first</option><option value="year">Year, oldest first</option></Select></Field></div></div>
      <p className={styles.hint}>Title search and sorting apply to this loaded page. Metadata filters below apply across the library.</p>
      <Disclosure title="Filter the library"><form onSubmit={event => { event.preventDefault(); if (!filterError(draft)) apply(draft); }}><div className={styles.filters}>{filterFields.map(([key, label, max]) => <Field key={key} id={`library-${key}`} label={label}><Input id={`library-${key}`} maxLength={max} inputMode={key.startsWith('year') ? 'numeric' : undefined} value={draft[key]} onChange={event => setDraft(previous => ({ ...previous, [key]: event.target.value }))} /></Field>)}</div>{filterError(draft) && <Banner tone="danger">{filterError(draft)}</Banner>}<div className={styles.actions}><Button type="submit" variant="secondary" disabled={Boolean(filterError(draft))}>Apply filters</Button><Button variant="quiet" onClick={() => apply(emptyFilters)}>Clear filters</Button></div></form></Disclosure>
    </div>{hasFilters && <div className={styles.chips} aria-label="Active library filters">{filterFields.filter(([key]) => filters[key].trim()).map(([key, label]) => <button type="button" className={styles.chip} key={key} aria-label={`Remove ${label} filter`} onClick={() => apply({ ...filters, [key]: '' })}>{label}: {filters[key]}<X size={12} aria-hidden="true" /></button>)}</div>}</Card>
    {documents.error && <ErrorBanner error={documents.error} baseUrl={preferences.baseUrl} onRetry={documents.refresh} />}
    {documents.pending ? <Card><Skeleton lines={6} /></Card> : documents.data && <Card>{loaded === 0 ? <EmptyState title={hasFilters ? 'No documents match these filters' : total > 0 ? 'This page is empty' : 'Your library is empty'}>{hasFilters ? 'Clear or adjust the metadata filters to browse other sources.' : total > 0 ? 'Go to the first page or refresh the library.' : canWrite ? <>Upload a document to start searching and asking questions. <Button variant="secondary" onClick={() => setOpen(true)}>Upload your first document</Button></> : 'Load documents with a write key to start searching and asking questions.'}</EmptyState> : rows.length === 0 ? <EmptyState title="No titles match on this page">Try another title, clear the title search, or browse another page. This search does not cover other pages.</EmptyState> : <><p className={`${styles.hint} ${styles.scrollHint}`}>Scroll the table horizontally to view all columns.</p><div className={styles.tableScroll} role="region" aria-label="Document library table" tabIndex={0}><table className={styles.table}><caption className={styles.hint}>Document metadata</caption><thead><tr><th scope="col">Title</th><th scope="col">Agency</th><th scope="col">Type</th><th scope="col">Year</th><th scope="col">Version</th><th scope="col">Chunks</th></tr></thead><tbody>{rows.map(document => <tr key={document.id}><td><span className={styles.title}>{document.title}</span><span className={styles.filename}>{document.filename}</span></td><td>{document.source_agency}</td><td>{document.doc_type}</td><td>{document.year}</td><td>{document.version}</td><td>{chunks.values[document.id] === 'error' ? <span title="Chunk count could not be loaded">—</span> : chunks.values[document.id] ?? <span aria-label="Loading chunk count">…</span>}</td></tr>)}</tbody></table></div></>}
      {Object.values(chunks.values).includes('error') && <Banner tone="warning">Some chunk counts could not be loaded. Document metadata remains available. <Button variant="quiet" onClick={chunks.retry}>Retry chunk counts</Button></Banner>}
      <div className={styles.pager}><p className={styles.hint} role="status">{total > 0 ? `Loaded ${loaded ? offset + 1 : 0}–${offset + loaded} of ${total} documents${query.trim() ? ` · ${rows.length} title matches on this page` : ''}` : '0 documents'}</p><label className={styles.pageSize}>Rows per page<Select aria-label="Rows per page" value={limit} onChange={event => { setLimit(Number(event.target.value)); setOffset(0); }}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></Select></label><div className={styles.actions}>{offset > 0 && <Button variant="quiet" onClick={() => setOffset(0)}>First page</Button>}<Button variant="secondary" aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - limit))}><ChevronLeft size={16} aria-hidden="true" />Previous</Button><Button variant="secondary" aria-label="Next page" disabled={offset + loaded >= total || loaded === 0} onClick={() => setOffset(value => value + limit)}>Next<ChevronRight size={16} aria-hidden="true" /></Button></div></div>
    </Card>}
    {canWrite && <UploadDrawer open={open} onClose={close} onAccepted={accepted} running={running} />}
  </div>;
}
