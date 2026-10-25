import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';

const temp = await mkdtemp(join(tmpdir(), 'docs-api-types-'));
try {
  const url = process.env.LABDOCS_OPENAPI_URL || 'http://127.0.0.1:8001/openapi.json';
  let schema;
  if (process.env.LABDOCS_OPENAPI_FILE) schema = await readFile(process.env.LABDOCS_OPENAPI_FILE, 'utf8');
  else {
    const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });
    if (!response.ok) throw new Error(`Schema request failed: HTTP ${response.status}`);
    schema = await response.text();
  }
  await writeFile(join(temp, 'openapi.json'), schema);
  execFileSync(process.execPath, [resolve('node_modules/openapi-typescript/bin/cli.js'), join(temp, 'openapi.json'), '-o', join(temp, 'api.ts')], { stdio: 'pipe' });
  const current = await readFile('src/types/api.ts', 'utf8');
  const generated = await readFile(join(temp, 'api.ts'), 'utf8');
  if (current !== generated) throw new Error('Generated API types are stale. Regenerate src/types/api.ts from the running API schema.');
  console.log('Generated API types match the current API schema.');
} finally { await rm(temp, { recursive: true, force: true }); }
