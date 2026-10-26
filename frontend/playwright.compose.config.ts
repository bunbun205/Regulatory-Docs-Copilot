import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: ['e2e/zz_journey.spec.ts', 'compose/*.spec.ts'],
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/compose-results.json' }]],
  outputDir: 'test-results/compose-artifacts',
  use: {
    baseURL: process.env.COMPOSE_BROWSER_URL || 'http://127.0.0.1:3300',
    trace: 'retain-on-failure', screenshot: 'only-on-failure', colorScheme: 'light',
  },
});
