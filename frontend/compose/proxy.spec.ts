import { test, expect } from '@playwright/test';

test('nginx serves the built SPA, proxies readiness, and keeps metrics private', async ({ page, request }) => {
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  expect((await request.get('/healthz')).status()).toBe(200);
  const ready = await request.get('/api/readyz');
  expect(ready.status()).toBe(200);
  expect(await ready.json()).toEqual({ status: 'ok', checks: { database: 'ok', qdrant: 'ok', embedder: 'ok' } });
  expect((await request.get('/api/metrics')).status()).toBe(404);
  expect((await request.get('/api/metrics/')).status()).toBe(404);
  expect((await request.get('/api/v1/whoami')).status()).toBe(401);
});

test('nginx streams oversized bodies to the API limit and preserves its error envelope', async ({ request }) => {
  const response = await request.post('/api/v1/search', {
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'compose-body-limit' },
    data: Buffer.alloc(26 * 1024 * 1024 + 1, 'x'),
  });
  expect(response.status()).toBe(413);
  expect(response.headers()['x-request-id']).toBe('compose-body-limit');
  const body = await response.json();
  expect(body.error.request_id).toBe('compose-body-limit');
  expect(body.error.code).toBe('payload_too_large');
});
