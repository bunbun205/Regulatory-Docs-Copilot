import { afterEach, beforeEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn().mockImplementation((query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
const NativeRequest = globalThis.Request;
beforeEach(() => {
  // Node's Request needs absolute URLs; browsers resolve the same-origin /api path.
  class BrowserRequest extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) { super(typeof input === 'string' ? new URL(input, location.href) : input, init); }
  }
  vi.stubGlobal('Request', BrowserRequest);
});
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); delete document.documentElement.dataset.theme; });
