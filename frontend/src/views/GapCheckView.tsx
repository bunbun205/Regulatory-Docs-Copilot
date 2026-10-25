import { useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSettings } from '../app/context';
import { multipart } from '../api/contracts';
import { useAsync } from '../hooks/useAsync';
import { usePolling } from '../hooks/usePolling';
import type { components } from '../types/api';
import { Banner, Button, EmptyState, ErrorBanner } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';

type Job = components['schemas']['GapCheckJobResponse'];
const terminal = (job: Job) => ['completed', 'failed', 'cancelled'].includes(job.status);

export default function GapCheckView() {
  const { api, preferences } = useSettings();
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const submitAction = useAsync<components['schemas']['GapCheckSubmitResponse']>();
  const cancelAction = useAsync<components['schemas']['GapCheckCancelResponse']>();
  const loadJob = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/gapcheck/{job_id}', { params: { path: { job_id: jobId ?? '' } }, signal })), [api, jobId]);
  const job = usePolling(loadJob, Boolean(jobId), 2000, terminal);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    void submitAction.run(async signal => {
      const result = await api.request(() => api.client.POST('/v1/gapcheck', { signal, body: { text: text.trim(), backend: preferences.backend }, bodySerializer: body => multipart(body ?? {}, null) }));
      if (result.ok && !signal.aborted) navigate(`/gap-check/${result.data.job_id}`);
      return result;
    });
  };
  if (jobId) return <div>
    <p style={{ overflowWrap: 'anywhere', fontSize: 12 }}>Run {jobId}</p>
    {job.pending && <p role="status">Loading run…</p>}
    {job.error && <ErrorBanner error={job.error} baseUrl={preferences.baseUrl} onRetry={job.refresh} />}
    {job.data && <><p role="status">Status: {job.data.status} · Clauses {job.data.progress.clauses_done} of {job.data.progress.clauses_total}</p>{!terminal(job.data) && <Button variant="secondary" disabled={cancelAction.pending || Boolean(cancelAction.data)} onClick={() => { void cancelAction.run(signal => api.request(() => api.client.POST('/v1/gapcheck/{job_id}/cancel', { signal, params: { path: { job_id: jobId } } }))); }}>{cancelAction.data ? 'Cancellation requested' : 'Cancel run'}</Button>}{job.data.error && <Banner tone="danger">{job.data.error}</Banner>}
    {job.data.report && <section><h2>Findings report</h2><Banner tone="warning">{job.data.report.banner}</Banner>{job.data.report.findings.map(finding => <div key={finding.finding_id} className="finding"><h3>{finding.finding_id} · {finding.verdict} · {finding.severity}</h3><p>{finding.rationale}</p><p>{finding.suggested_fix}</p>{finding.regulation_citations.map(citation => <p key={citation.chunk_id}>{citation.title}{citation.page !== null && ` · Page ${citation.page}`}</p>)}</div>)}</section>}</>}
    <RequestStatus action={cancelAction} baseUrl={preferences.baseUrl} canStop={false} /><p><Button variant="quiet" onClick={() => navigate('/gap-check')}>Start another gap check</Button></p>
  </div>;
  return <div><form onSubmit={submit}><label htmlFor="sop-text">SOP text</label><textarea id="sop-text" rows={10} value={text} onChange={event => setText(event.target.value)} placeholder="Paste the SOP you want to review…" disabled={submitAction.pending} /><button type="submit" disabled={submitAction.pending || submitAction.retryIn > 0 || !text.trim()}>Run gap check</button></form><RequestStatus action={submitAction} baseUrl={preferences.baseUrl} canStop={false} /><EmptyState title="A second look at your SOP">Check a procedure against the regulations in your loaded library. Findings support your review; they do not establish compliance.</EmptyState></div>;
}
