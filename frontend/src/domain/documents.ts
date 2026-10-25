import type { components } from '../types/api';
import { record } from '../api/errors';

export type Document = components['schemas']['DocumentSummary'];
export type IngestionJob = components['schemas']['IngestionJobResponse'];
export type UploadMetadata = Omit<components['schemas']['Body_upload_document_v1_documents_post'], 'file' | 'year'> & { year: string };
export const ingestionTerminal = (job: IngestionJob) => job.status === 'completed' || job.status === 'failed';
export const reindexCommand = 'python -m app.cli reindex --backend qdrant';
export function documentFileError(file: Pick<File, 'name' | 'size'> | null) {
  if (!file) return 'Choose a document.';
  if (!/\.(pdf|md|markdown|txt)$/i.test(file.name)) return 'Choose a PDF, Markdown or TXT document.';
  if (file.name.length > 512) return 'The file name must be at most 512 characters.';
  if (file.size === 0) return 'The document is empty.';
  if (file.size > 25 * 1024 * 1024) return 'The document exceeds the 25 MiB default precheck limit.';
}
export function metadataErrors(values: UploadMetadata): Partial<Record<keyof UploadMetadata, string>> {
  const errors: Partial<Record<keyof UploadMetadata, string>> = {};
  for (const [key, max] of [['title', 500], ['source_agency', 200], ['doc_type', 100], ['version', 200]] as const) {
    if (!values[key].trim()) errors[key] = 'This field is required.';
    else if (values[key].length > max) errors[key] = `Use at most ${max} characters.`;
  }
  if (!/^\d{4}$/.test(values.year) || Number(values.year) < 1900 || Number(values.year) > 2100) errors.year = 'Use a whole year from 1900 to 2100.';
  return errors;
}
export type DocumentSort = 'newest' | 'title' | 'title-desc' | 'year' | 'year-desc';
export function pageDocuments(documents: Document[], query: string, sort: DocumentSort) {
  const needle = query.trim().toLocaleLowerCase();
  const result = documents.filter(document => document.title.toLocaleLowerCase().includes(needle));
  const tie = (a: Document, b: Document) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
  if (sort === 'title') result.sort(tie);
  if (sort === 'title-desc') result.sort((a, b) => -tie(a, b));
  if (sort === 'year') result.sort((a, b) => a.year - b.year || tie(a, b));
  if (sort === 'year-desc') result.sort((a, b) => b.year - a.year || tie(a, b));
  return result;
}
export function count(value: unknown): number | null { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null; }
export function reportRows(value: unknown): Record<string, unknown>[] { return Array.isArray(value) ? value.flatMap(item => { const row = record(item); return row ? [row] : []; }) : []; }
export function stringList(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []; }
export function syncWarning(job: IngestionJob): boolean {
  // This is the existing pipeline's explicit post-commit failure message, not a
  // claim inferred from a completed status or an invented report field.
  const supplied = [job.error, ...reportRows(job.report?.failures).map(row => row.reason)].filter((value): value is string => typeof value === 'string');
  return supplied.some(message => /Postgres committed/i.test(message) && /Qdrant index is out of date/i.test(message));
}
