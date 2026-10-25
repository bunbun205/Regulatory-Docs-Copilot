import { useCallback, useState } from 'react';
import { useSettings } from '../app/context';
import { multipart } from '../api/contracts';
import { useAsync } from '../hooks/useAsync';
import { usePolling } from '../hooks/usePolling';
import type { components } from '../types/api';
import { Banner, EmptyState, ErrorBanner } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';

type Job = components['schemas']['IngestionJobResponse'];
const terminal = (job: Job) => ['completed', 'failed'].includes(job.status);

export default function DocumentsView() {
  const { api, identity, preferences } = useSettings();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [sourceAgency, setSourceAgency] = useState('');
  const [docType, setDocType] = useState('guidance');
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [version, setVersion] = useState('v1');
  const upload = useAsync<components['schemas']['UploadResponse']>();
  const jobId = upload.data?.job_id;
  const loadJob = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/jobs/{job_id}', { params: { path: { job_id: jobId ?? '' } }, signal })), [api, jobId]);
  const job = usePolling(loadJob, Boolean(jobId), 2000, terminal);
  const running = Boolean(jobId) && (!job.data || !terminal(job.data));
  const loadDocuments = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/documents', { signal })), [api]);
  const documents = usePolling(loadDocuments, true, running ? 2000 : 60_000);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return;
    void upload.run(signal => api.request(() => api.client.POST('/v1/documents', { signal, body: { file: file.name, title, source_agency: sourceAgency, doc_type: docType, year, version }, bodySerializer: body => multipart(body, file) })));
  };
  return <div>
    {identity?.scopes.includes('write') ? <section><h2>Upload document</h2><form onSubmit={submit}>
      <div className="form-group"><label htmlFor="document-file">File</label><input id="document-file" type="file" accept=".pdf,.md,.markdown,.txt" onChange={event => setFile(event.target.files?.[0] || null)} required disabled={upload.pending || running} /></div>
      <div className="form-group"><label htmlFor="document-title">Title</label><input id="document-title" value={title} onChange={event => setTitle(event.target.value)} required /></div>
      <div className="form-group"><label htmlFor="document-agency">Source agency</label><input id="document-agency" value={sourceAgency} onChange={event => setSourceAgency(event.target.value)} required /></div>
      <div className="form-group"><label htmlFor="document-type">Document type</label><select id="document-type" value={docType} onChange={event => setDocType(event.target.value)}><option value="guidance">Guidance</option><option value="regulation">Regulation</option><option value="policy">Policy</option></select></div>
      <div className="form-group"><label htmlFor="document-year">Year</label><input id="document-year" type="number" min={1900} max={2100} value={year} onChange={event => setYear(Number(event.target.value))} required /></div>
      <div className="form-group"><label htmlFor="document-version">Version</label><input id="document-version" value={version} onChange={event => setVersion(event.target.value)} required /></div>
      <button type="submit" disabled={upload.pending || upload.retryIn > 0 || running}>Upload document</button>
    </form><RequestStatus action={upload} baseUrl={preferences.baseUrl} canStop={false} />{jobId && <p role="status">Upload status: {job.data?.status ?? 'queued'}</p>}{job.error && <ErrorBanner error={job.error} baseUrl={preferences.baseUrl} onRetry={job.refresh} />}{job.data?.error && <Banner tone="danger">{job.data.error}</Banner>}</section> : <Banner title="Uploads need write access">{identity ? 'This key is read only. You can still browse the document library.' : 'Validate your key in Settings to check upload access.'}</Banner>}
    <section><h2>Document library</h2>{documents.error && <ErrorBanner error={documents.error} baseUrl={preferences.baseUrl} onRetry={documents.refresh} />}{documents.pending ? <p role="status">Loading documents…</p> : documents.data?.items.length === 0 ? <EmptyState title="Your library is empty">Load documents with a write key to start searching and asking questions.</EmptyState> : <div className="table-scroll" role="region" aria-label="Document library table" tabIndex={0}><table><thead><tr><th>Title</th><th>Agency</th><th>Type</th><th>Year</th><th>Version</th><th>File</th></tr></thead><tbody>{documents.data?.items.map(document => <tr key={document.id}><td>{document.title}</td><td>{document.source_agency}</td><td>{document.doc_type}</td><td>{document.year}</td><td>{document.version}</td><td>{document.filename}</td></tr>)}</tbody></table></div>}</section>
  </div>;
}
