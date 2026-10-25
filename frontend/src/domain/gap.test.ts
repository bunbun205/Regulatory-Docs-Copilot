import { describe, expect, it, vi } from 'vitest';
import { downloadReport, fileError, filteredFindings, findingFilters, markdownText, reportMarkdown, reportMetadata } from './gap';
import { gapFinding, gapReport } from '../test/gap';
const all = { severity: '', direction: '', verdict: '', q: '' };
describe('Gap report rules', () => {
  it('sorts severity then clause order rather than lexical finding IDs', () => {
    const report = { ...gapReport, findings: [{ ...gapFinding, finding_id: 'GAP-0009', severity: 'low' as const }, { ...gapFinding, finding_id: 'GAP-0002', sop_clause_refs: ['SOP-002'] }, { ...gapFinding, finding_id: 'GAP-0010', sop_clause_refs: ['SOP-001'] }] };
    expect(filteredFindings(report, all).map(f => f.finding_id)).toEqual(['GAP-0010', 'GAP-0002', 'GAP-0009']);
  });
  it('combines all filters and searches SOP text and regulation excerpts', () => {
    expect(filteredFindings(gapReport, { ...all, severity: 'high', direction: 'sop_to_regulation', verdict: 'conflict', q: 'INSTRUMENT' }).map(f => f.finding_id)).toEqual(['GAP-0001']);
    expect(filteredFindings(gapReport, { ...all, q: 'invalid citations' }).map(f => f.verdict)).toEqual(['judge_failed']);
    expect(filteredFindings(gapReport, { ...all, direction: 'regulation_to_sop' })).toEqual([]);
  });
  it('ignores invalid URL enums and does not turn manual review into a pass', () => {
    expect(findingFilters(new URLSearchParams('severity=critical&direction=sideways&verdict=judge_failed&q=log'))).toEqual({ ...all, verdict: 'judge_failed', q: 'log' });
    expect(filteredFindings(gapReport, { ...all, verdict: 'compliant' })).toEqual([]);
  });
  it('narrows unknown metadata without coercing objects, booleans or numeric strings', () => {
    const meta = reportMetadata({ model: { name: 'wrong' }, backend: false, duration_ms: '3', token_usage: { total_tokens: -1, input_tokens: NaN }, caps: [] });
    expect(meta.model).toBeNull(); expect(meta.backend).toBeNull(); expect(meta.duration).toBeNull(); expect(meta.totalTokens).toBeNull(); expect(meta.inputTokens).toBeNull(); expect(meta.maxClauses).toBeNull();
    expect(reportMetadata(gapReport.metadata).totalTokens).toBe(28);
  });
  it('validates file extension, empty content and default size without trusting MIME', () => {
    expect(fileError({ name: 'SOP.PDF', size: 100 })).toBeUndefined(); expect(fileError({ name: 'sop.exe', size: 100 })).toMatch(/PDF/); expect(fileError({ name: 'sop.md', size: 0 })).toMatch(/empty/); expect(fileError({ name: 'sop.txt', size: 25 * 1024 * 1024 + 1 })).toMatch(/25 MiB/);
  });
  it('exports every finding, clause, excerpt, disclaimer and safe Markdown text', () => {
    const report = { ...gapReport, findings: [{ ...gapFinding, rationale: '<img src=x> [click](javascript:alert(1))', suggested_fix: '<script>bad()</script>' }], caps_hit: ['requirements'] };
    const markdown = reportMarkdown(report); expect(markdown).toContain(markdownText(gapReport.banner)); expect(markdown).toContain('SOP\\-002'); expect(markdown).toContain('Staff must record instrument checks'); expect(markdown).toContain('&lt;img src=x&gt;'); expect(markdown).not.toContain('<script>'); expect(markdown).not.toContain('[click](javascript:'); expect(markdown).toContain('requirements'); expect(markdownText('`<b>x</b>`')).toBe('\\`&lt;b&gt;x&lt;/b&gt;\\`');
    expect(JSON.parse(JSON.stringify(report))).toEqual(report);
  });
  it('preserves source provenance, requirement context, limits and unlinked clauses in Markdown', () => {
    const report = { ...gapReport, findings: [{ ...gapFinding, requirement_id: 'REQ-002' }], caps_hit: ['requirements'] };
    const markdown = reportMarkdown(report);
    expect(markdown).toContain('Requirement ID: REQ\\-002');
    expect(markdown).toContain('Requirement strength: mandatory');
    for (const citation of gapFinding.regulation_citations) {
      expect(markdown).toContain(markdownText(citation.document_id));
      expect(markdown).toContain(markdownText(citation.chunk_id));
      expect(markdown).toContain(markdownText(citation.snippet));
    }
    for (const clause of report.sop_clauses) expect(markdown).toContain(markdownText(clause.text));
    expect(markdown).toContain('Input tokens: 20'); expect(markdown).toContain('Output tokens: 8');
    expect(markdown).toContain('Requirement cap: 120'); expect(markdown).toContain('analysis may be incomplete');
    expect(markdown).toContain('Failed judgements are unresolved');
  });
  it('makes a client download and releases its object URL', () => {
    vi.useFakeTimers(); const create = vi.fn(() => 'blob:test-report'); const revoke = vi.fn(); vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke })); const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    downloadReport('{}', 'report.json', 'application/json'); expect(create.mock.calls[0]).toBeDefined(); expect(click).toHaveBeenCalledOnce(); expect(document.querySelector('a[download]')).toBeNull(); vi.runAllTimers(); expect(revoke).toHaveBeenCalledWith('blob:test-report');
  });
});
