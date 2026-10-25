export type Theme = 'system' | 'light' | 'dark';
export type Preferences = { baseUrl: string; backend: 'pgvector' | 'qdrant'; topK: number; theme: Theme };
export const DEFAULTS: Preferences = { baseUrl: '/api', backend: 'pgvector', topK: 2, theme: 'system' };
export const KEY_STORAGE = 'labdocs_api_key';
const PREFS_STORAGE = 'docs_copilot_preferences';

export function normalizeBaseUrl(value: string): string {
  const input = value.trim().replace(/\/+$/, '');
  if (input.startsWith('/') && !input.startsWith('//') && !/[?#\\]/.test(input)) return input || '/api';
  let parsed: URL;
  try { parsed = new URL(input); } catch { throw new Error('Use a path such as /api or a complete http:// or https:// address.'); }
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error('Use an HTTP address without credentials, query parameters or a fragment.');
  }
  return input;
}

export function loadPreferences(): Preferences {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(PREFS_STORAGE) || '{}');
    if (!stored || typeof stored !== 'object') return DEFAULTS;
    const value = stored as Record<string, unknown>;
    return {
      baseUrl: typeof value.baseUrl === 'string' ? normalizeBaseUrl(value.baseUrl) : DEFAULTS.baseUrl,
      backend: value.backend === 'qdrant' ? 'qdrant' : 'pgvector',
      topK: typeof value.topK === 'number' && Number.isInteger(value.topK) && value.topK >= 1 && value.topK <= 50 ? value.topK : DEFAULTS.topK,
      theme: value.theme === 'light' || value.theme === 'dark' ? value.theme : 'system',
    };
  } catch { return DEFAULTS; }
}
export function savePreferences(value: Preferences) {
  try { localStorage.setItem(PREFS_STORAGE, JSON.stringify(value)); } catch { /* In-memory settings remain usable if storage is disabled. */ }
}
export function loadKey() { try { return sessionStorage.getItem(KEY_STORAGE) || ''; } catch { return ''; } }
export function saveKey(value: string) { try { if (value) sessionStorage.setItem(KEY_STORAGE, value); else sessionStorage.removeItem(KEY_STORAGE); } catch { /* The key still works for this page lifetime. */ } }
