import type { ApiError } from '../../api/errors';
import { Banner, Button, ElapsedTimer, ErrorBanner, Spinner } from '.';

type Action = { pending: boolean; stopped: boolean; startedAt: number | null; error: ApiError | null; stop: () => void; retry: () => void };
export default function RequestStatus({ action, baseUrl, canStop = true }: { action: Action; baseUrl: string; canStop?: boolean }) {
  return <div style={{ display: 'grid', gap: 16, marginTop: 16 }}>
    {action.pending && <div role="status" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}><Spinner /><span>Working…</span><ElapsedTimer startedAt={action.startedAt} />{canStop && <Button variant="quiet" onClick={action.stop}>Stop waiting</Button>}</div>}
    {action.stopped && <Banner>Stopped waiting. The server may keep working.</Banner>}
    {action.error && <ErrorBanner error={action.error} baseUrl={baseUrl} onRetry={action.retry} />}
  </div>;
}
