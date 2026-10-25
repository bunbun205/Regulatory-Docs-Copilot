import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import App from './App';
import SettingsProvider from './app/SettingsProvider';
import { KEY_STORAGE } from './app/storage';

function mount(path: string) { return render(<MemoryRouter initialEntries={[path]}><SettingsProvider><App /></SettingsProvider></MemoryRouter>); }

describe('foundation integration', () => {
  it('routes a 401 to Settings with an explanatory shared error', async () => {
    sessionStorage.setItem(KEY_STORAGE, 'invalid-test-key');
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => request.url.endsWith('/readyz') ? Response.json({ status: 'ok', checks: { database: 'ok' } }) : Response.json({ error: { code: 'unauthorized', message: 'Invalid key.', request_id: 'redirect-test' } }, { status: 401 })));
    mount('/ask');
    await screen.findByRole('heading', { level: 1, name: 'Settings' });
    expect((await screen.findByRole('alert')).textContent).toContain('Validate a key in Settings');
  });
  it('uses the selected base URL, key and defaults in a feature request', async () => {
    sessionStorage.setItem(KEY_STORAGE, 'private-test-value'); localStorage.setItem('docs_copilot_preferences', JSON.stringify({ baseUrl: '/custom', backend: 'qdrant', topK: 12, theme: 'light' }));
    const requests: Request[] = [];
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      requests.push(request);
      if (request.url.endsWith('/readyz')) return Response.json({ status: 'ok', checks: { database: 'ok' } });
      if (request.url.endsWith('/whoami')) return Response.json({ name: 'reader', scopes: ['read'] });
      return Response.json({ results: [], backend: 'qdrant' });
    }));
    mount('/search'); const input = await screen.findByLabelText('Search your library'); fireEvent.change(input, { target: { value: 'records' } }); fireEvent.submit(input.closest('form')!);
    await screen.findByText('No passages found');
    const request = requests.find(item => item.url.endsWith('/v1/search'))!;
    expect(request.url).toContain('/custom/v1/search'); expect(request.headers.get('X-API-Key')).toBe('private-test-value'); expect(await request.json()).toEqual({ query: 'records', backend: 'qdrant', top_k: 12 });
  });
  it('Stop waiting aborts locally and shows no error or late result', async () => {
    sessionStorage.setItem(KEY_STORAGE, 'private-test-value'); let signal: AbortSignal | null = null;
    vi.stubGlobal('fetch', vi.fn(async (request: Request, init?: RequestInit) => {
      if (request.url.endsWith('/readyz')) return Response.json({ status: 'ok', checks: { database: 'ok' } });
      if (request.url.endsWith('/whoami')) return Response.json({ name: 'reader', scopes: ['read'] });
      signal = init?.signal ?? null;
      return new Promise<Response>((_resolve, reject) => signal?.addEventListener('abort', () => reject(signal?.reason)));
    }));
    mount('/search'); const input = await screen.findByLabelText('Search your library'); fireEvent.change(input, { target: { value: 'records' } }); fireEvent.submit(input.closest('form')!);
    await waitFor(() => expect(signal).not.toBeNull()); fireEvent.click(screen.getByRole('button', { name: 'Stop waiting' }));
    expect((signal as AbortSignal | null)?.aborted).toBe(true); expect(screen.getByText(/The server may keep working/)).toBeTruthy(); expect(screen.queryByRole('alert')).toBeNull();
  });
});
