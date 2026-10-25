import type { components } from '../types/api';
import type { ApiResult } from '../api/client';

export type Citation = components['schemas']['AskCitation'];
export type SearchHit = components['schemas']['SearchResult'];
export type Backend = 'pgvector' | 'qdrant';
export type FilterValues = { agency: string; type: string; yearMin: string; yearMax: string };
export const emptyFilters: FilterValues = { agency: '', type: '', yearMin: '', yearMax: '' };
export function filterError(values: FilterValues): string | undefined {
  for (const value of [values.yearMin, values.yearMax]) if (value && (!/^\d{4}$/.test(value) || Number(value) < 1900 || Number(value) > 2100)) return 'Years must be whole numbers from 1900 to 2100.';
  if (values.yearMin && values.yearMax && Number(values.yearMin) > Number(values.yearMax)) return 'Start year must be no later than end year.';
}
export function apiFilters(values: FilterValues): components['schemas']['SearchFiltersRequest'] | undefined {
  const filters = { ...(values.agency.trim() && { source_agency: values.agency.trim() }), ...(values.type.trim() && { doc_type: values.type.trim() }), ...(values.yearMin && { year_min: Number(values.yearMin) }), ...(values.yearMax && { year_max: Number(values.yearMax) }) };
  return Object.keys(filters).length ? filters : undefined;
}
export function validTopK(value: string) { return /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 50; }
export type AnswerPart = { text: string } | { citation: number };
export function citationParts(text: string, count: number): AnswerPart[] {
  const parts: AnswerPart[] = []; let offset = 0;
  for (const match of text.matchAll(/\[([1-9]\d*)\]/g)) {
    const index = Number(match[1]);
    if (index > count) continue;
    if (match.index > offset) parts.push({ text: text.slice(offset, match.index) });
    parts.push({ citation: index }); offset = match.index + match[0].length;
  }
  if (offset < text.length) parts.push({ text: text.slice(offset) });
  return parts;
}
export function overlap(left: SearchHit[], right: SearchHit[]) {
  const a = new Set(left.map(hit => hit.chunk_id)); const b = new Set(right.map(hit => hit.chunk_id));
  return { shared: [...a].filter(id => b.has(id)).length, total: new Set([...a, ...b]).size };
}
export function answerMarkdown(answer: string, citations: Citation[]) {
  return `${answer}${citations.length ? '\n\nSources (supplied excerpts):\n' + citations.map((c, i) => `[${i + 1}] ${c.title}${c.page !== null ? `, page ${c.page}` : ''}\n${c.snippet}`).join('\n\n') : ''}`;
}
export type Run<T> = { payload: T; requestId: string | null };
export function runResult<T>(result: ApiResult<T>): ApiResult<Run<T>> {
  return result.ok ? { ...result, data: { payload: result.data, requestId: result.response.headers.get('X-Request-ID') } } : result.cancelled ? result : { ok: false, error: result.error, body: result.body, response: result.response };
}
export type HistoryItem = { question: string; answer: string };
const HISTORY = 'docs_copilot_ask_history';
export function readHistory(): HistoryItem[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(HISTORY) || '[]');
    return Array.isArray(value) ? value.filter((item): item is HistoryItem => item !== null && typeof item === 'object' && typeof item.question === 'string' && typeof item.answer === 'string').slice(0, 10) : [];
  } catch { return []; }
}
export function saveHistory(items: HistoryItem[]) { try { sessionStorage.setItem(HISTORY, JSON.stringify(items.slice(0, 10))); } catch { /* The current answer remains usable when storage is full. */ } }
