import { describe, expect, it, vi } from 'vitest';
import { createApi } from './client';

function response(value: unknown, status = 200, headers = {}) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json', ...headers } }); }

describe('typed request wrapper', () => {
  it('sends key in the header and uses the configured address', async () => {
    const fetcher = vi.fn(async (_request: Request) => response({ name: 'review', scopes: ['read'] })); vi.stubGlobal('fetch', fetcher);
    const api = createApi('http://127.0.0.1:8001', 'private-test-value');
    const result = await api.request(() => api.client.GET('/v1/whoami'));
    expect(result.ok).toBe(true);
    const request = fetcher.mock.calls[0][0] as unknown as Request;
    expect(request.url).toBe('http://127.0.0.1:8001/v1/whoami'); expect(request.headers.get('X-API-Key')).toBe('private-test-value');
    expect(request.url).not.toContain('private-test-value');
  });
  it('notifies unauthorized and returns a safe typed error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ error: { code: 'unauthorized', message: 'No access' } }, 401)));
    const unauthorized = vi.fn(); const api = createApi('http://api.test', 'key', unauthorized);
    const result = await api.request(() => api.client.GET('/v1/whoami'));
    expect(result.ok).toBe(false); expect(unauthorized).toHaveBeenCalledTimes(1);
    if (!result.ok) expect(result.error?.status).toBe(401);
  });
  it('keeps partial/ungrounded HTTP 200 data intact for the view to label', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ answer: 'Partial answer', partial: true, partial_reason: 'timeout', grounded: false, trace: [] })));
    const api = createApi('http://api.test', 'key'); const result = await api.request(() => api.client.POST('/v1/agent/run', { body: { query: 'question' } }));
    expect(result.ok && result.data.partial).toBe(true); expect(result.ok && result.data.grounded).toBe(false);
  });
  it('normalizes network failures without leaking exception details', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('sensitive provider text'); }));
    const api = createApi('http://api.test', 'key'); const result = await api.request(() => api.client.GET('/v1/whoami'));
    if (result.ok) throw new Error('Expected error');
    expect(result.error?.status).toBe(0); expect(result.error?.message).not.toContain('sensitive');
  });
  it('times out the transport and distinguishes user abort from errors', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn((_request: Request, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal;
      if (signal?.aborted) reject(signal.reason);
      else signal?.addEventListener('abort', () => reject(signal.reason));
    })));
    const api = createApi('http://api.test', 'key', () => {}, 1000);
    const pending = api.request(() => api.client.GET('/v1/whoami'));
    await vi.advanceTimersByTimeAsync(1000); const timeout = await pending;
    expect(!timeout.ok && timeout.error?.code).toBe('timeout');
    const controller = new AbortController();
    const cancelled = api.request(() => api.client.GET('/v1/whoami', { signal: controller.signal }));
    controller.abort(); const result = await cancelled;
    expect(result).toEqual({ ok: false, cancelled: true });
  });
});
