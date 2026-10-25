import { defineConfig } from '@playwright/test';
import base from './playwright.config.js';

export default defineConfig({
  ...base, testMatch: '**/performance.spec.ts', testIgnore: [], timeout: 90_000,
  reporter: [['list'], ['json', { outputFile: 'test-results/performance-results.json' }]],
  webServer: [
    { command: '../.venv/bin/uvicorn frontend.e2e.server:app --app-dir .. --host 127.0.0.1 --port 8001', url: 'http://127.0.0.1:8001/readyz', timeout: 120_000, reuseExistingServer: false, env: { FRONTEND_E2E_LARGE_CORPUS: '1' } },
    { command: 'npm run dev -- --host 127.0.0.1 --port 3100 --strictPort', url: 'http://127.0.0.1:3100', env: { LABDOCS_API_PROXY_TARGET: 'http://127.0.0.1:8001' }, timeout: 30_000, reuseExistingServer: false },
  ],
});
