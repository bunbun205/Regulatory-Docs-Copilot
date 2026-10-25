import type { ReactNode } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import SettingsProvider from '../app/SettingsProvider';
import type { components } from '../types/api';
import { KEY_STORAGE } from '../app/storage';

export const citation: components['schemas']['AskCitation'] = { chunk_id: 'chunk-a', document_id: 'document-a', title: 'Instrument checks', page: 3, snippet: 'Staff must record instrument checks.', score: 0.82 };
export const hit: components['schemas']['SearchResult'] = { ...citation, text: citation.snippet, chunk_index: 0, section_heading: 'Training', filename: 'training.txt', source_agency: 'Test agency', doc_type: 'training', year: 2026, version: 'v1' };
export const ask: components['schemas']['AskResponse'] = { query: 'What must staff record?', backend: 'pgvector', answer: 'Record instrument checks. [1]', citations: [citation], grounded: true, grounding_reason: null, insufficient_evidence: false, top_score: 0.82, usage: { input_tokens: 20, output_tokens: 8, total_tokens: 28 }, latency_ms: { retrieve_ms: 30, generate_ms: 400 } };
export function mockResearch(handler: (request: Request, init?: RequestInit) => Promise<Response>) {
  const fetcher = vi.fn(async (request: Request, init?: RequestInit) => {
    if (request.url.endsWith('/whoami')) return Response.json({ name: 'reader', scopes: ['read'] });
    if (request.url.endsWith('/readyz')) return Response.json({ status: 'ok', checks: { database: 'ok' } });
    if (request.url.endsWith('/documents/document-a')) return Response.json({ id: 'document-a', ...hit, chunk_count: 1 });
    return handler(request, init);
  });
  vi.stubGlobal('fetch', fetcher); return fetcher;
}
export function mountResearch(children: ReactNode, route = '/ask') {
  sessionStorage.setItem(KEY_STORAGE, 'frontend-unit-key');
  return render(<MemoryRouter initialEntries={[route]}><SettingsProvider>{children}</SettingsProvider></MemoryRouter>);
}
