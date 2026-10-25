import { readFile, writeFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';

const manifest = JSON.parse(await readFile('dist/.vite/manifest.json', 'utf8'));
const initial = new Set();
function add(key) { const entry = manifest[key]; if (!entry || initial.has(entry.file)) return; initial.add(entry.file); for (const dependency of entry.imports || []) add(dependency); }
add('index.html');
// The default route additionally loads Ask and its shared lazy dependencies.
add('src/views/AskView.tsx');
const chunks = [];
for (const file of initial) if (file.endsWith('.js')) chunks.push({ file, gzip_bytes: gzipSync(await readFile(`dist/${file}`)).byteLength });
const total = chunks.reduce((sum, item) => sum + item.gzip_bytes, 0);
const report = { route: '/ask', chunks, total_gzip_bytes: total, budget_gzip_bytes: 110_000 };
console.log(JSON.stringify(report, null, 2));
if (process.argv[2]) await writeFile(process.argv[2], JSON.stringify(report, null, 2) + '\n');
if (total > 110_000) { console.error('Initial route JS exceeds the 110 kB gzip budget.'); process.exitCode = 1; }
