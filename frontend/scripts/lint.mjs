import { execFileSync } from 'node:child_process';

let output;
try { output = execFileSync('node_modules/.bin/oxlint', ['--format', 'json'], { encoding: 'utf8' }); }
catch (error) { output = String(error.stdout || '{}'); process.exitCode = 1; }
const report = JSON.parse(output);
const allowed = new Set(['react(purity)']);
const seen = new Set();
for (const item of report.diagnostics || []) {
  const known = item.severity === 'warning' && item.filename === 'src/views/DocumentsView.tsx' && allowed.has(item.code) && !seen.has(item.code);
  seen.add(item.code);
  console.log(`${item.filename}: ${item.severity} ${item.code}: ${item.message}${known ? ' (existing; clear by F5)' : ''}`);
  if (!known) process.exitCode = 1;
}
if (!process.exitCode) console.log('No new lint warnings or errors.');
