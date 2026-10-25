import { describe, expect, it } from 'vitest';
import { count, documentFileError, metadataErrors, pageDocuments, syncWarning } from './documents';
import { document, ingestionJob } from '../test/documents';
const metadata = { title: 'Training', source_agency: 'Agency', doc_type: 'guidance', year: '2026', version: 'v1' };
describe('Document contract rules', () => {
  it('validates real API field bounds and rejects blank metadata and fractional years', () => {
    expect(metadataErrors(metadata)).toEqual({});
    expect(metadataErrors({ ...metadata, title: ' ', source_agency: 'x'.repeat(201), year: '2026.5', version: '' })).toHaveProperty('year');
    expect(Object.keys(metadataErrors({ ...metadata, title: ' ', source_agency: 'x'.repeat(201), year: '2026.5', version: '' }))).toHaveLength(4);
    expect(metadataErrors({ ...metadata, year: '1900', doc_type: 'custom local type' })).toEqual({});
    expect(metadataErrors({ ...metadata, year: '2101' }).year).toBeTruthy();
  });
  it('accepts all four existing document extensions and checks file name, empty and size limits', () => {
    for (const name of ['x.PDF', 'x.md', 'x.markdown', 'x.txt']) expect(documentFileError({ name, size: 2 })).toBeUndefined();
    expect(documentFileError(null)).toMatch(/Choose/); expect(documentFileError({ name: 'x.exe', size: 2 })).toMatch(/PDF/);
    expect(documentFileError({ name: 'x.txt', size: 0 })).toMatch(/empty/); expect(documentFileError({ name: 'x.txt', size: 25 * 1024 * 1024 + 1 })).toMatch(/25 MiB/);
    expect(documentFileError({ name: 'x'.repeat(513) + '.txt', size: 1 })).toMatch(/512/);
  });
  it('searches only supplied page titles and sorts without mutating server order', () => {
    const items = [{ ...document, id: 'b', title: 'Zulu', year: 2020 }, { ...document, id: 'a', title: 'Alpha', year: 2025 }];
    expect(pageDocuments(items, ' ALP ', 'newest').map(item => item.id)).toEqual(['a']);
    expect(pageDocuments(items, 'training.md', 'title')).toEqual([]);
    expect(pageDocuments(items, '', 'title').map(item => item.id)).toEqual(['a', 'b']);
    expect(pageDocuments(items, '', 'year-desc').map(item => item.id)).toEqual(['a', 'b']);
    expect(items[0].id).toBe('b');
  });
  it('narrows report counts without inventing zeroes or coercing strings', () => {
    for (const value of [undefined, null, true, -1, 2.5, '2', NaN, Infinity, {}]) expect(count(value)).toBeNull();
    expect(count(0)).toBe(0); expect(count(2)).toBe(2);
  });
  it('requires the supplied post-commit Qdrant message before recommending reindex', () => {
    expect(syncWarning(ingestionJob)).toBe(false);
    expect(syncWarning({ ...ingestionJob, error: 'Qdrant unavailable before ingestion.' })).toBe(false);
    const reason = 'Postgres committed this document, but the qdrant index is out of date.';
    expect(syncWarning({ ...ingestionJob, status: 'failed', error: reason })).toBe(true);
    expect(syncWarning({ ...ingestionJob, report: { failures: [{ reason }] } })).toBe(true);
  });
});
