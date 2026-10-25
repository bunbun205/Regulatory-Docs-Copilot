import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Check, Clock3 } from 'lucide-react';
import { useSettings } from '../../app/context';
import { useAsync } from '../../hooks/useAsync';
import { usePolling } from '../../hooks/usePolling';
import type { components } from '../../types/api';
import { isTerminal } from '../../domain/gap';
import type { GapJob as Job } from '../../domain/gap';
import { Badge, Banner, Button, Card, ElapsedTimer, EmptyState, ErrorBanner, Skeleton } from '../ui';
import RequestStatus from '../ui/RequestStatus';
import GapReport from './GapReport';
import research from '../research/research.module.css';
import styles from './gap.module.css';

const phases = [{ phase: 'queued', label: 'Read the SOP', detail: 'Waiting to read and segment the SOP.' }, { phase: 'clauses', label: 'Check SOP clauses', detail: 'Compare each clause with retrieved regulations.' }, { phase: 'requirements', label: 'Check regulation requirements', detail: 'Look for omissions in the SOP.' }, { phase: 'finalizing', label: 'Build the report', detail: 'Collect findings and run details.' }];
function Progress({ job }: { job: Job }) {
  const index = phases.findIndex(item => item.phase === job.progress.phase);
  const started = Date.parse(job.started_at ?? job.created_at);
  return <Card><div className={styles.statusLine}><h2 className={styles.title}>Review in progress</h2><Badge><Clock3 size={13} aria-hidden="true" />{job.status === 'queued' ? 'Queued' : 'Running'}</Badge></div><p className={styles.lead}>This page resumes the run when you reload. Progress shows the last confirmed update.</p><ol className={styles.progress}>{phases.map((phase, i) => <li className={`${styles.phase} ${i === index ? styles.current : ''} ${i < index ? styles.finished : ''}`} key={phase.phase} aria-current={i === index ? 'step' : undefined}><span className={styles.phaseNumber}>{i < index ? <Check size={14} aria-hidden="true" /> : i + 1}</span><div><p>{phase.label}</p><small>{i < index && phase.phase === 'queued' ? 'SOP read and segmented.' : phase.detail}</small>{phase.phase === 'clauses' && job.progress.clauses_total > 0 && <><small>Clause {job.progress.clauses_done} of {job.progress.clauses_total}</small><progress className={styles.progressMeter} aria-label="SOP clauses checked" value={job.progress.clauses_done} max={job.progress.clauses_total} /></>}{phase.phase === 'requirements' && job.progress.phase !== 'queued' && job.progress.phase !== 'clauses' && <><small>Requirement {job.progress.requirements_done} of {job.progress.requirements_total}</small>{job.progress.requirements_total > 0 && <progress className={styles.progressMeter} aria-label="Requirements checked" value={job.progress.requirements_done} max={job.progress.requirements_total} />}</>}</div></li>)}</ol><ElapsedTimer startedAt={Number.isFinite(started) ? started : null} /><p className={research.hint} style={{ marginTop: 12 }}>Any reported limits are shown with the finished report.</p></Card>;
}
export default function GapJob({ jobId }: { jobId: string }) {
  const { api, preferences } = useSettings(); const cancel = useAsync<components['schemas']['GapCheckCancelResponse']>();
  const load = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/gapcheck/{job_id}', { signal, params: { path: { job_id: jobId } } })), [api, jobId]);
  const polling = usePolling(load, true, 2000, isTerminal); const job = polling.data;
  const active = job && !isTerminal(job);
  return <div className={styles.stack}><div className={`${styles.statusLine} ${styles.noPrint}`}><p className={styles.runId}>Run {jobId}</p><Link to="/gap-check">Start another gap check</Link></div>{polling.pending && <Card><p role="status">Loading run…</p><Skeleton lines={5} /></Card>}{polling.error && <div className={styles.stack}><ErrorBanner error={polling.error} baseUrl={preferences.baseUrl} onRetry={polling.refresh} />{job && <Banner tone="warning">Status updates failed. The information below is the last confirmed state; the server may still be working.</Banner>}</div>}
    {job && <>{active && <><Progress job={job} /><div className={research.actions}><Button variant="secondary" disabled={cancel.pending || Boolean(cancel.data?.cancel_requested)} onClick={() => { void cancel.run(signal => api.request(() => api.client.POST('/v1/gapcheck/{job_id}/cancel', { signal, params: { path: { job_id: jobId } } }))); }}>{cancel.data?.cancel_requested ? 'Cancellation requested' : 'Cancel run'}</Button><p className={research.hint}>Cancellation takes effect between bounded steps.</p></div>{cancel.data?.cancel_requested && <Banner>Cancellation requested. Waiting for the server to confirm a terminal state.</Banner>}</>}
    {job.status === 'failed' && <Banner tone="danger" title="This run failed">{job.error || 'The run could not finish. Review the input and try a new run.'}</Banner>}
    {job.status === 'cancelled' && <Banner tone="warning" title="Run cancelled">The server confirmed cancellation. Any report shown below may be incomplete.</Banner>}
    {job.error && job.status !== 'failed' && job.status !== 'cancelled' && <Banner tone="danger">{job.error}</Banner>}
    {job.report ? <GapReport report={job.report} /> : job.status === 'completed' ? <EmptyState title="The run finished without a report">The API did not return a findings report. Start a new run or review the API response.</EmptyState> : (job.status === 'failed' || job.status === 'cancelled') && <EmptyState title="No report is available for this run">You can adjust the SOP or scope and start another run.</EmptyState>}
    </>}
    <div className={styles.noPrint}><RequestStatus action={cancel} baseUrl={preferences.baseUrl} canStop={false} /></div>
  </div>;
}
