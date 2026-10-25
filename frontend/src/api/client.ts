import createClient from 'openapi-fetch';
import type { paths } from '../types/api';
import { ApiError, record, responseError } from './errors';

export type ApiResult<T> = { ok: true; data: T; response: Response }
  | { ok: false; error: ApiError; cancelled?: false; data?: T; body?: unknown; response?: Response }
  | { ok: false; cancelled: true; error?: never };

type Operation<T> = () => Promise<{ data?: T; error?: unknown; response: Response }>;

export function createApi(baseUrl: string, key: string, unauthorized: (error: ApiError) => void = () => {}, timeoutMs = 190_000) {
  const client = createClient<paths>({
    baseUrl,
    fetch: async (request: Request) => {
      const controller = new AbortController();
      const abort = () => controller.abort(request.signal.reason);
      if (request.signal.aborted) abort();
      else request.signal.addEventListener('abort', abort, { once: true });
      const timer = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs);
      try { return await fetch(request, { signal: controller.signal }); }
      finally { clearTimeout(timer); request.signal.removeEventListener('abort', abort); }
    },
  });
  client.use({ onRequest({ request }) { if (key) request.headers.set('X-API-Key', key); return request; } });

  async function request<T>(operation: Operation<T>): Promise<ApiResult<T>> {
    try {
      const result = await operation();
      if (!result.response.ok) {
        const error = responseError(result.response, result.error, key);
        if (error.status === 401) unauthorized(error);
        return { ok: false, error, body: result.error, response: result.response };
      }
      if (result.data === undefined) return { ok: false, error: new ApiError(502, 'invalid_response', 'The API returned an empty response.') };
      return { ok: true, data: result.data, response: result.response };
    } catch (cause) {
      const name = record(cause)?.name;
      if (name === 'AbortError') return { ok: false, cancelled: true };
      const timeout = name === 'TimeoutError';
      return { ok: false, error: new ApiError(timeout ? 504 : 0, timeout ? 'timeout' : 'network_error', timeout ? 'The request timed out.' : 'The API could not be reached.') };
    }
  }
  return { client, request };
}

export type Api = ReturnType<typeof createApi>;
