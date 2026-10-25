import { describe, expect, it } from 'vitest';
import { ApiError, errorDetails, errorMessage, responseError, retrySeconds } from './errors';

describe('API errors', () => {
  it.each([401, 403, 422, 429, 502, 503, 504])('maps HTTP %s and preserves safe details', status => {
    const response = new Response('{}', { status, headers: { 'X-Request-ID': 'request-123', 'Retry-After': '3' } });
    const error = responseError(response, { error: { code: 'test_code', message: 'Server message.' } });
    expect(error.status).toBe(status); expect(error.requestId).toBe('request-123'); expect(error.retryAfter).toBe(3);
    expect(errorMessage(error, '/api').length).toBeGreaterThan(10);
    expect(errorDetails(error)).toContain('test_code');
  });
  it('accepts missing, non-JSON and malformed envelopes without inventing field details', () => {
    for (const body of [null, 'proxy error', [], { error: { message: 42 } }]) {
      expect(responseError(new Response('', { status: 500 }), body).message).toBe('Request failed (HTTP 500).');
    }
  });
  it('redacts a key from all copied fields and prefers envelope request id', () => {
    const key = 'private-test-value';
    const error = responseError(new Response('', { status: 401, headers: { 'X-Request-ID': 'header' } }), { error: { code: key, message: `Echo ${key}`, request_id: `request-${key}` } }, key);
    expect(errorDetails(error)).not.toContain(key); expect(error.requestId).toBe('request-[redacted]');
  });
  it('maps network failure and timeout in plain language', () => {
    expect(errorMessage(new ApiError(0, 'network_error', 'network'), '/custom-api')).toContain("Can't reach the API at /custom-api");
    expect(errorMessage(new ApiError(504, 'timeout', 'timeout'), '/api')).toContain('took too long');
  });
  it('parses Retry-After seconds, date, expired and invalid values', () => {
    expect(retrySeconds('2.2')).toBe(3); expect(retrySeconds('-1')).toBe(0);
    expect(retrySeconds('Sun, 25 Oct 2026 12:00:03 GMT', Date.parse('2026-10-25T12:00:00Z'))).toBe(3);
    expect(retrySeconds('Sun, 25 Oct 2026 11:00:00 GMT', Date.parse('2026-10-25T12:00:00Z'))).toBe(0);
    expect(retrySeconds('not a time')).toBeNull(); expect(retrySeconds(null)).toBeNull();
  });
});
