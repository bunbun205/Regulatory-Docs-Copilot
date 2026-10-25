import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createApi } from '../api/client';
import type { ApiResult } from '../api/client';
import { ApiError, record } from '../api/errors';
import { usePolling } from '../hooks/usePolling';
import { SettingsContext } from './context';
import type { Identity, ReadyData } from './context';
import { loadKey, loadPreferences, normalizeBaseUrl, saveKey, savePreferences } from './storage';
import type { Preferences } from './storage';

export default function SettingsProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(loadPreferences);
  const [key, setKey] = useState(loadKey);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [unauthorized, setUnauthorized] = useState<ApiError | null>(null);
  const generation = useRef(0);
  const onUnauthorized = useCallback((error: ApiError) => { setIdentity(null); setUnauthorized(error); }, []);
  const api = useMemo(() => createApi(preferences.baseUrl, key, onUnauthorized), [preferences.baseUrl, key, onUnauthorized]);
  const [initialApi] = useState(() => createApi(preferences.baseUrl, key));
  const updatePreferences = useCallback((changes: Partial<Preferences>) => {
    setPreferences(previous => ({ ...previous, ...changes }));
  }, []);
  useEffect(() => { savePreferences(preferences); }, [preferences]);
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const apply = () => { document.documentElement.dataset.theme = preferences.theme === 'system' ? (media.matches ? 'dark' : 'light') : preferences.theme; };
    apply(); media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [preferences.theme]);
  useEffect(() => {
    const controller = new AbortController();
    const token = generation.current;
    if (loadKey()) void initialApi.request(() => initialApi.client.GET('/v1/whoami', { signal: controller.signal })).then(result => {
      if (controller.signal.aborted || token !== generation.current) return;
      if (result.ok) setIdentity(result.data);
      else if (!result.cancelled && result.error.status === 401) onUnauthorized(result.error);
    });
    return () => controller.abort();
  }, [initialApi, onUnauthorized]);
  const validate = useCallback(async (baseUrl: string, value: string, signal: AbortSignal) => {
    const normalized = normalizeBaseUrl(baseUrl);
    const saved = value.trim();
    if (saved && normalized.includes(saved)) return { ok: false as const, error: new ApiError(422, 'invalid_api_address', 'Keep your API key out of the address.') };
    const token = ++generation.current;
    setKey(saved); saveKey(saved); setIdentity(null); setUnauthorized(null);
    updatePreferences({ baseUrl: normalized });
    const candidate = createApi(normalized, saved, error => { if (token === generation.current && !signal.aborted) onUnauthorized(error); });
    const result = await candidate.request(() => candidate.client.GET('/v1/whoami', { signal }));
    if (result.ok && token === generation.current && !signal.aborted) setIdentity(result.data);
    return result;
  }, [updatePreferences, onUnauthorized]);
  const forget = useCallback(() => { generation.current++; setKey(''); saveKey(''); setIdentity(null); setUnauthorized(null); }, []);
  const loadReady = useCallback(async (signal: AbortSignal): Promise<ApiResult<ReadyData>> => {
    const result = await api.request(() => api.client.GET('/readyz', { signal }));
    if (!result.ok && result.cancelled) return result;
    const root = record(result.ok ? result.data : result.body);
    const checks = record(root?.checks);
    if (typeof root?.status !== 'string' || !checks) return !result.ok ? { ok: false, error: result.error } : { ok: false, error: new ApiError(502, 'invalid_readiness', 'The API returned an unreadable readiness response.') };
    const data: ReadyData = { status: root.status, checks: Object.fromEntries(Object.entries(checks).filter((entry): entry is [string, string] => typeof entry[1] === 'string')) };
    return { ...result, data };
  }, [api]);
  // Restart readiness polling if the configured address changes; keys never enter URLs.
  const readiness = usePolling(loadReady, true, 30_000);
  return <SettingsContext.Provider value={{ preferences, updatePreferences, key, identity, unauthorized, api, validate, forget, readiness }}>{children}</SettingsContext.Provider>;
}
