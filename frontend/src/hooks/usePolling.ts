import { useCallback, useEffect, useRef, useState } from 'react';
import type { ApiResult } from '../api/client';
import { ApiError } from '../api/errors';

export function usePolling<T>(load: (signal: AbortSignal) => Promise<ApiResult<T>>, active = true, interval = 2000, terminal?: (data: T) => boolean) {
  const cooldown = useRef(0);
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<{ data: T | null; error: ApiError | null; loader: typeof load | null }>({ data: null, error: null, loader: null });
  const refresh = useCallback(() => { if (cooldown.current <= Date.now()) setVersion(v => v + 1); }, []);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      let result: ApiResult<T>;
      try { result = await load(controller.signal); }
      catch { result = { ok: false, error: new ApiError(0, 'polling_error', 'The status update could not be completed.') }; }
      if (controller.signal.aborted) return;
      if (result.ok) {
        cooldown.current = 0;
        setState({ data: result.data, error: null, loader: load });
        if (terminal?.(result.data)) return;
      } else if (!result.cancelled) {
        setState(s => ({ data: result.data ?? (s.loader === load ? s.data : null), error: result.error, loader: load }));
        cooldown.current = Date.now() + (result.error.retryAfter ?? 0) * 1000;
      }
      timer = setTimeout(() => { void tick(); }, Math.max(interval, cooldown.current - Date.now()));
    }
    void Promise.resolve().then(tick);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [active, interval, version, load, terminal]);
  return { data: state.loader === load ? state.data : null, error: state.loader === load ? state.error : null, pending: active && state.loader !== load, refresh };
}
