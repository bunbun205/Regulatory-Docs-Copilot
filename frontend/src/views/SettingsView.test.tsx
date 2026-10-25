import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import SettingsProvider from '../app/SettingsProvider';
import SettingsView from './SettingsView';
import DocumentsView from './DocumentsView';
import { KEY_STORAGE } from '../app/storage';

function mockApi(scopes = ['read', 'write']) {
  const fetcher = vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path.endsWith('/readyz')) return Response.json({ status: 'ok', checks: { database: 'ok', qdrant: 'ok' } });
    if (path.endsWith('/whoami')) {
      const valid = request.headers.get('X-API-Key') === 'private-test-value';
      return valid ? Response.json({ name: 'review-key', scopes }) : Response.json({ error: { code: 'unauthorized', message: 'Invalid API key.', request_id: 'invalid-key-test' } }, { status: 401 });
    }
    if (path.endsWith('/documents')) return Response.json({ items: [], total: 0 });
    return Response.json({});
  });
  vi.stubGlobal('fetch', fetcher); return fetcher;
}
function mount(children = <SettingsView />) { return render(<MemoryRouter><SettingsProvider>{children}</SettingsProvider></MemoryRouter>); }

describe('Settings and scope flow', () => {
  it('ignores a late 401 from a previous key after a new key validates', async () => {
    sessionStorage.setItem(KEY_STORAGE, 'previous-bad-key');
    let rejectOld!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      if (request.url.endsWith('/readyz')) return Response.json({ status: 'ok', checks: { database: 'ok' } });
      if (request.headers.get('X-API-Key') === 'previous-bad-key') return new Promise<Response>(resolve => { rejectOld = resolve; });
      return Response.json({ name: 'new-key', scopes: ['read'] });
    }));
    mount(); await waitFor(() => expect(rejectOld).toBeDefined());
    fireEvent.change(screen.getByLabelText('API key', { exact: true }), { target: { value: 'new-key-value' } });
    fireEvent.submit(screen.getByRole('button', { name: 'Validate key' }).closest('form')!);
    await screen.findByText('Read-only key', { exact: true });
    await act(async () => rejectOld(Response.json({ error: { code: 'unauthorized', message: 'Old key.' } }, { status: 401 })));
    expect(screen.queryByRole('alert')).toBeNull(); expect(screen.getByText('Read-only key', { exact: true })).toBeTruthy();
  });
  it('shows failed readiness checks alongside their HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ status: 'error', checks: { database: 'unavailable' } }, { status: 503 })));
    mount();
    await screen.findByText('PostgreSQL'); expect(screen.getByText('unavailable', { exact: true })).toBeTruthy(); expect(screen.getByRole('alert')).toBeTruthy();
  });
  it('validates a key, shows effective scopes/readiness and never persists the key locally', async () => {
    mockApi(); const user = userEvent.setup(); mount();
    await user.type(screen.getByLabelText('API key', { exact: true }), 'private-test-value');
    await user.click(screen.getByRole('button', { name: 'Validate key' }));
    await screen.findByText('Connection verified', { exact: true });
    expect(screen.getAllByText('review-key').length).toBeGreaterThan(0); expect(screen.getByText('Read & write', { exact: true })).toBeTruthy();
    expect(screen.getByText('PostgreSQL')).toBeTruthy(); expect(screen.getByText('Qdrant', { selector: 'span' })).toBeTruthy();
    expect(sessionStorage.getItem(KEY_STORAGE)).toBe('private-test-value');
    expect(JSON.stringify(localStorage)).not.toContain('private-test-value');
  });
  it('shows a shared invalid-key error with copyable request details', async () => {
    mockApi(); const user = userEvent.setup(); mount();
    await user.type(screen.getByLabelText('API key', { exact: true }), 'bad-value');
    await user.click(screen.getByRole('button', { name: 'Validate key' }));
    await screen.findByRole('alert'); expect(screen.getByRole('alert').textContent).toContain('Your API key is missing or invalid');
    expect(screen.getByRole('button', { name: 'Copy details' })).toBeTruthy(); expect(screen.getByRole('alert').textContent).toContain('invalid-key-test');
  });
  it('supports show/hide and forget without clearing preferences', async () => {
    mockApi(); sessionStorage.setItem(KEY_STORAGE, 'private-test-value'); const user = userEvent.setup(); mount();
    await screen.findByText('Connection verified', { exact: true });
    const input = screen.getByLabelText('API key', { exact: true }); expect(input.getAttribute('type')).toBe('password');
    await user.click(screen.getByRole('button', { name: 'Show API key' })); expect(input.getAttribute('type')).toBe('text');
    await user.click(screen.getByRole('button', { name: 'Dark' })); expect(document.documentElement.dataset.theme).toBe('dark');
    await user.click(screen.getByRole('button', { name: 'Forget key' })); expect(sessionStorage.getItem(KEY_STORAGE)).toBeNull(); expect(input.getAttribute('type')).toBe('password');
    expect(JSON.parse(localStorage.getItem('docs_copilot_preferences') || '{}').theme).toBe('dark');
  });
  it('explains read-only access and hides the upload form', async () => {
    mockApi(['read']); sessionStorage.setItem(KEY_STORAGE, 'private-test-value'); mount(<><SettingsView /><DocumentsView /></>);
    await screen.findByText('Read-only key', { exact: true }); expect(screen.getByText('Uploads require write access')).toBeTruthy();
    expect(screen.queryByLabelText('File', { exact: true })).toBeNull();
  });
  it('validates local fields without sending the key in an address', async () => {
    const fetcher = mockApi(); const user = userEvent.setup(); mount();
    await user.click(screen.getByRole('button', { name: 'Validate key' })); expect(screen.getByText('Enter an API key to validate.')).toBeTruthy();
    await user.type(screen.getByLabelText('API key', { exact: true }), 'private-test-value');
    await user.clear(screen.getByLabelText('API base URL')); await user.type(screen.getByLabelText('API base URL'), '/api/private-test-value');
    await user.click(screen.getByRole('button', { name: 'Validate key' })); expect(screen.getByText(/Keep your API key out of the address/)).toBeTruthy();
    expect(fetcher.mock.calls.every(([request]) => !request.url.includes('private-test-value'))).toBe(true);
  });
  it('saves a valid source count and rejects an empty one', async () => {
    mockApi(); mount();
    const count = screen.getByLabelText('Default source count'); fireEvent.change(count, { target: { value: '' } });
    fireEvent.submit(screen.getByRole('button', { name: 'Save defaults' }).closest('form')!); expect(screen.getByText('Choose a whole number from 1 to 50.')).toBeTruthy();
    fireEvent.change(count, { target: { value: '12' } }); fireEvent.submit(screen.getByRole('button', { name: 'Save defaults' }).closest('form')!);
    await waitFor(() => expect(JSON.parse(localStorage.getItem('docs_copilot_preferences') || '{}').topK).toBe(12));
  });
});
