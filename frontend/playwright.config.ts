import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', testMatch: '**/*.spec.ts', testIgnore: '**/performance.spec.ts', fullyParallel: false, workers: 1,
  timeout: 45_000, retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  outputDir: 'test-results/artifacts',
  use: { baseURL: 'http://127.0.0.1:3100', trace: 'retain-on-failure', screenshot: 'only-on-failure', colorScheme: 'light' },
  webServer: [
    { command: '../.venv/bin/uvicorn frontend.e2e.server:app --app-dir .. --host 127.0.0.1 --port 8001', url: 'http://127.0.0.1:8001/readyz', timeout: 60_000, reuseExistingServer: false },
    { command: 'npm run dev -- --host 127.0.0.1 --port 3100 --strictPort', url: 'http://127.0.0.1:3100', env: { LABDOCS_API_PROXY_TARGET: 'http://127.0.0.1:8001' }, timeout: 30_000, reuseExistingServer: false },
  ],
});
