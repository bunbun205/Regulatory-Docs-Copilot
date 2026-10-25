export class ApiError extends Error {
  public readonly occurredAt = Date.now();
  public status: number;
  public code: string;
  public requestId: string | null;
  public retryAfter: number | null;
  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null = null,
    retryAfter: number | null = null,
  ) { super(message); this.name = 'ApiError'; this.status = status; this.code = code; this.requestId = requestId; this.retryAfter = retryAfter; }
}

export function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

export function redact(text: string, key: string): string {
  return key ? text.split(key).join('[redacted]') : text;
}

export function retrySeconds(value: string | null, now = Date.now()): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, Math.ceil(seconds));
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, Math.ceil((date - now) / 1000));
}

export function responseError(response: Response, body: unknown, key = ''): ApiError {
  const envelope = record(record(body)?.error);
  const code = typeof envelope?.code === 'string' ? envelope.code : `http_${response.status}`;
  const message = typeof envelope?.message === 'string' ? envelope.message : `Request failed (HTTP ${response.status}).`;
  const id = typeof envelope?.request_id === 'string' ? envelope.request_id : response.headers.get('X-Request-ID');
  return new ApiError(response.status, redact(code, key), redact(message, key), id ? redact(id, key) : null, retrySeconds(response.headers.get('Retry-After')));
}

export function errorMessage(error: ApiError, baseUrl: string): string {
  if (error.status === 401) return 'Your API key is missing or invalid. Validate a key in Settings to continue.';
  if (error.status === 403) return "Your key doesn't allow this action.";
  if (error.status === 429) return 'Too many requests. Give the API a moment before trying again.';
  if ([502, 503, 504].includes(error.status) || error.code === 'timeout') return 'The language model took too long or a required service is unavailable. You can try again.';
  if (error.status === 0) return `Can't reach the API at ${baseUrl}. Check the address and that the local services are running.`;
  if (error.status === 422) return `Please check the form. ${error.message}`;
  return error.message;
}

export function errorDetails(error: ApiError): string {
  return JSON.stringify({ status: error.status, code: error.code, message: error.message, requestId: error.requestId }, null, 2);
}
