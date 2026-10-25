import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAsync } from './useAsync';
import { usePolling } from './usePolling';
import { ApiError } from '../api/errors';
import type { ApiResult } from '../api/client';

const success = (value: string): ApiResult<string> => ({ ok: true, data: value, response: new Response('{}') });

describe('useAsync', () => {
  it('prevents duplicate submissions, aborts waiting and ignores a late response', async () => {
    let finish!: (value: ApiResult<string>) => void;
    const operation = vi.fn((_signal: AbortSignal) => new Promise<ApiResult<string>>(resolve => { finish = resolve; }));
    const { result } = renderHook(() => useAsync<string>());
    await act(async () => { void result.current.run(operation); void result.current.run(operation); });
    expect(operation).toHaveBeenCalledTimes(1); expect(result.current.pending).toBe(true);
    act(() => result.current.stop()); expect(operation.mock.calls[0][0].aborted).toBe(true);
    await act(async () => finish(success('late')));
    expect(result.current.data).toBeNull(); expect(result.current.error).toBeNull(); expect(result.current.stopped).toBe(true);
    await act(async () => { await result.current.run(async () => success('new')); });
    expect(result.current.data).toBe('new'); expect(result.current.stopped).toBe(false);
  });
  it('respects Retry-After before allowing resubmit or retry', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useAsync<string>());
    const operation = vi.fn(async (): Promise<ApiResult<string>> => ({ ok: false, error: new ApiError(429, 'rate_limited', 'Wait', null, 2) }));
    await act(async () => { await result.current.run(operation); });
    expect(result.current.retryIn).toBe(2);
    await act(async () => { await result.current.run(operation); result.current.retry(); });
    expect(operation).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(result.current.retryIn).toBe(0);
    await act(async () => { result.current.retry(); }); expect(operation).toHaveBeenCalledTimes(2);
  });
  it('aborts on unmount and clears pending state after unexpected failure', async () => {
    const { result, unmount } = renderHook(() => useAsync<string>());
    await act(async () => { await result.current.run(async () => { throw new Error('private detail'); }); });
    expect(result.current.pending).toBe(false); expect(result.current.error?.message).not.toContain('private');
    let signal: AbortSignal | null = null;
    await act(async () => { void result.current.run(current => { signal = current; return new Promise(() => {}); }); });
    unmount(); expect((signal as AbortSignal | null)?.aborted).toBe(true);
  });
});

describe('usePolling', () => {
  it('never overlaps requests and stops at a terminal state', async () => {
    vi.useFakeTimers();
    let finish!: (value: ApiResult<string>) => void;
    const load = vi.fn((_signal: AbortSignal): Promise<ApiResult<string>> => new Promise(resolve => { finish = resolve; }));
    const done = (value: string) => value === 'done';
    const { result } = renderHook(() => usePolling(load, true, 2000, done));
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); }); expect(load).toHaveBeenCalledTimes(1);
    await act(async () => finish(success('running')));
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); }); expect(load).toHaveBeenCalledTimes(2);
    await act(async () => finish(success('done')));
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); }); expect(load).toHaveBeenCalledTimes(2); expect(result.current.data).toBe('done');
  });
  it('makes polling failures visible, honors Retry-After and aborts on unmount', async () => {
    vi.useFakeTimers();
    const load = vi.fn(async (_signal: AbortSignal): Promise<ApiResult<string>> => ({ ok: false, error: new ApiError(429, 'rate_limited', 'Wait', null, 5) }));
    const { result, unmount } = renderHook(() => usePolling(load, true, 2000));
    await act(async () => { await Promise.resolve(); }); expect(result.current.error?.status).toBe(429);
    await act(async () => { result.current.refresh(); await vi.advanceTimersByTimeAsync(4000); }); expect(load).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); }); expect(load).toHaveBeenCalledTimes(2);
    unmount(); expect(load.mock.calls[0][0].aborted).toBe(true);
  });
  it('rejects stale data when its loader changes', async () => {
    let finish!: (value: ApiResult<string>) => void;
    const old = (_signal: AbortSignal) => new Promise<ApiResult<string>>(resolve => { finish = resolve; });
    const next = async (_signal: AbortSignal) => success('new address');
    const { result, rerender } = renderHook(({ load }) => usePolling(load), { initialProps: { load: old } });
    await act(async () => { await Promise.resolve(); });
    rerender({ load: next }); await act(async () => { await Promise.resolve(); });
    await act(async () => finish(success('stale address'))); expect(result.current.data).toBe('new address');
    const failed = async (_signal: AbortSignal): Promise<ApiResult<string>> => ({ ok: false, error: new ApiError(503, 'unavailable', 'Unavailable') });
    rerender({ load: failed }); await act(async () => { await Promise.resolve(); }); expect(result.current.data).toBeNull();
  });
});
