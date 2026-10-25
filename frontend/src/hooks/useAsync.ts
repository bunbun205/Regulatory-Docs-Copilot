import { useCallback, useEffect, useRef, useState } from 'react';
import type { ApiResult } from '../api/client';
import { ApiError } from '../api/errors';

export function useAsync<T>() {
  const [state, setState] = useState<{ data: T | null; error: ApiError | null; pending: boolean; startedAt: number | null; retryIn: number }>({ data: null, error: null, pending: false, startedAt: null, retryIn: 0 });
  const cooldown = useRef(0);
  const [stopped, setStopped] = useState(false);
  const active = useRef<AbortController | null>(null);
  const last = useRef<((signal: AbortSignal) => Promise<ApiResult<T>>) | null>(null);
  const stop = useCallback(() => { if (active.current) setStopped(true); active.current?.abort(); active.current = null; setState(s => ({ ...s, pending: false, startedAt: null })); }, []);
  const run = useCallback(async (operation: (signal: AbortSignal) => Promise<ApiResult<T>>) => {
    if (active.current || cooldown.current > Date.now()) return;
    const controller = new AbortController();
    active.current = controller;
    setStopped(false);
    last.current = operation;
    setState({ data: null, error: null, pending: true, startedAt: Date.now(), retryIn: 0 });
    try {
      const result = await operation(controller.signal);
      if (active.current !== controller || controller.signal.aborted) return;
      const error = !result.ok && !result.cancelled ? result.error : null;
      const retryIn = error?.retryAfter ?? 0;
      cooldown.current = Date.now() + retryIn * 1000;
      setState({ data: result.ok ? result.data : null, error, pending: false, startedAt: null, retryIn });
    } catch {
      if (active.current === controller && !controller.signal.aborted) setState({ data: null, error: new ApiError(0, 'request_error', 'The request could not be completed.'), pending: false, startedAt: null, retryIn: 0 });
    } finally {
      if (active.current === controller) active.current = null;
    }
  }, []);
  const retry = useCallback(() => { if (last.current) void run(last.current); }, [run]);
  const clear = useCallback(() => { stop(); setStopped(false); cooldown.current = 0; setState({ data: null, error: null, pending: false, startedAt: null, retryIn: 0 }); }, [stop]);
  useEffect(() => {
    if (!state.error?.retryAfter) return;
    const timer = setInterval(() => {
      const retryIn = Math.max(0, Math.ceil((cooldown.current - Date.now()) / 1000));
      setState(previous => ({ ...previous, retryIn }));
      if (retryIn === 0) clearInterval(timer);
    }, 250);
    return () => clearInterval(timer);
  }, [state.error]);
  useEffect(() => () => { active.current?.abort(); active.current = null; }, []);
  return { ...state, stopped, run, retry, stop, clear };
}
