import type { components } from '../types/api';
import { record } from '../api/errors';
export type GapJob = components['schemas']['GapCheckJobResponse'];
export type GapReport = components['schemas']['GapCheckReport'];
export type Finding = components['schemas']['GapCheckFinding'];
export type Verdict = Finding['verdict'];
export const verdictLabels: Record<Verdict, string> = { compliant: 'Compliant', partial: 'Partial', conflict: 'Conflict', missing: 'Missing', addressed: 'Addressed', partially_addressed: 'Partially addressed', judge_failed: 'Needs manual review', not_covered_by_corpus: 'Outside loaded documents' };
export const directionLabels: Record<Finding['direction'], string> = { sop_to_regulation: 'SOP → regulation', regulation_to_sop: 'Regulation → SOP' };
export const severityLabels = { high: 'High', medium: 'Medium', low: 'Low' };
export const verdicts = Object.keys(verdictLabels) as Verdict[];
export const isTerminal = (job: GapJob) => ['completed', 'failed', 'cancelled'].includes(job.status);
export const DEFAULT_UPLOAD_BYTES = 25 * 1024 * 1024;
export const DEFAULT_SOP_CHARS = 200_000;
export function fileError(file: Pick<File, 'name' | 'size'> | null): string | undefined {
  if (!file) return 'Choose an SOP file.';
  if (!/\.(pdf|md|txt)$/i.test(file.name)) return 'Choose a PDF, Markdown (.md) or text (.txt) file.';
  if (file.size === 0) return 'The file is empty.';
  if (file.size > DEFAULT_UPLOAD_BYTES) return 'The file exceeds the 25 MiB local precheck limit.';
}
export type FindingFilters = { severity: string; direction: string; verdict: string; q: string };
export function findingFilters(params: URLSearchParams): FindingFilters {
  const severity = params.get('severity') ?? ''; const direction = params.get('direction') ?? ''; const verdict = params.get('verdict') ?? '';
  return { severity: Object.hasOwn(severityLabels, severity) ? severity : '', direction: Object.hasOwn(directionLabels, direction) ? direction : '', verdict: Object.hasOwn(verdictLabels, verdict) ? verdict : '', q: (params.get('q') ?? '').slice(0, 2000) };
}
export function filteredFindings(report: GapReport, filters: FindingFilters): Finding[] {
  const order = new Map(report.sop_clauses.map((clause, i) => [clause.clause_id, i]));
  const index = (finding: Finding) => Math.min(...finding.sop_clause_refs.map(id => order.get(id) ?? Number.MAX_SAFE_INTEGER), Number.MAX_SAFE_INTEGER);
  const rank = { high: 0, medium: 1, low: 2 }; const query = filters.q.trim().toLocaleLowerCase();
  return report.findings.filter(finding => (!filters.severity || finding.severity === filters.severity) && (!filters.direction || finding.direction === filters.direction) && (!filters.verdict || finding.verdict === filters.verdict) && (!query || [finding.finding_id, finding.rationale, finding.suggested_fix, ...finding.regulation_citations.map(citation => `${citation.title} ${citation.snippet}`), ...report.sop_clauses.filter(clause => finding.sop_clause_refs.includes(clause.clause_id)).map(clause => `${clause.section} ${clause.text}`)].join(' ').toLocaleLowerCase().includes(query))).sort((a, b) => rank[a.severity] - rank[b.severity] || index(a) - index(b) || a.finding_id.localeCompare(b.finding_id, undefined, { numeric: true }));
}
function text(value: unknown): string | null { return typeof value === 'string' && value.trim() ? value : null; }
export function nonnegative(value: unknown): number | null { return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null; }
export function reportMetadata(metadata: GapReport['metadata']) {
  const tokens = record(metadata.token_usage); const caps = record(metadata.caps);
  return { model: text(metadata.model), backend: text(metadata.backend), duration: nonnegative(metadata.duration_ms), inputTokens: nonnegative(tokens?.input_tokens), outputTokens: nonnegative(tokens?.output_tokens), totalTokens: nonnegative(tokens?.total_tokens), maxClauses: nonnegative(caps?.max_clauses), maxRequirements: nonnegative(caps?.max_requirements), maxTokens: nonnegative(caps?.max_tokens) };
}
export function markdownText(value: string) { return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replace(/[\\`*_{}[\]()#+.!|~-]/g, '\\$&'); }
export function reportMarkdown(report: GapReport) {
  const md = markdownText; const metadata = reportMetadata(report.metadata);
  const lines = ['# SOP gap check', '', md(report.banner), '', `Run: ${md(report.job_id)}`, `Generated: ${md(report.generated_at)}`, '', '## Run details', ''];
  if (metadata.model) lines.push(`Model: ${md(metadata.model)}`);
  if (metadata.backend) lines.push(`Backend: ${md(metadata.backend)}`);
  if (metadata.duration !== null) lines.push(`Duration: ${(metadata.duration / 1000).toFixed(2)} s`);
  if (metadata.totalTokens !== null) lines.push(`Reported tokens: ${metadata.totalTokens}`);
  lines.push(`Caps reported: ${report.caps_hit.map(md).join(', ') || 'None reported'}`, '', '## Summary', '');
  for (const severity of ['high', 'medium', 'low'] as const) lines.push(`${severityLabels[severity]}: ${report.counts_by_severity[severity] ?? 0}`);
  for (const verdict of verdicts) lines.push(`${verdictLabels[verdict]}: ${report.counts_by_verdict[verdict] ?? 0}`);
  for (const finding of filteredFindings(report, { severity: '', direction: '', verdict: '', q: '' })) {
    lines.push('', `## ${md(finding.finding_id)} — ${verdictLabels[finding.verdict]}`, '', `${severityLabels[finding.severity]} · ${directionLabels[finding.direction]}`, '', '### SOP clauses', '');
    for (const id of finding.sop_clause_refs) { const clause = report.sop_clauses.find(item => item.clause_id === id); lines.push(`${md(id)}${clause ? ` — ${md(clause.section)}\n\n${md(clause.text)}` : ' — Clause text not supplied.'}`, ''); }
    if (!finding.sop_clause_refs.length) lines.push('No SOP clause was linked.', '');
    lines.push('### Regulation excerpts', '');
    for (const citation of finding.regulation_citations) lines.push(`${md(citation.title)}${citation.page !== null ? `, page ${citation.page}` : ''}\n\n${md(citation.snippet)}`, '');
    if (!finding.regulation_citations.length) lines.push('No regulation excerpt was supplied.', '');
    lines.push('### Rationale', '', md(finding.rationale), '', '### Suggestion, not legal advice', '', md(finding.suggested_fix));
  }
  if (!report.findings.length) lines.push('', 'No findings were returned. This does not establish compliance.');
  return lines.join('\n') + '\n';
}
export function downloadReport(contents: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type })); const link = document.createElement('a');
  link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 0);
}
