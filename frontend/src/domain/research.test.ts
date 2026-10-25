import { describe, expect, it } from 'vitest';
import { apiFilters, citationParts, filterError, overlap, readHistory, saveHistory, validTopK } from './research';
import { hit } from '../test/research';

describe('research presentation rules', () => {
  it('parses only positive, in-range citation markers and preserves all other text', () => {
    expect(citationParts('A [1] B [99] [0] [-1] [01] <b>text</b> [2]', 2)).toEqual([{ text: 'A ' }, { citation: 1 }, { text: ' B [99] [0] [-1] [01] <b>text</b> ' }, { citation: 2 }]);
    expect(citationParts('No placement supplied.', 2)).toEqual([{ text: 'No placement supplied.' }]);
  });
  it('keeps markers as text when no citations are supplied', () => { expect(citationParts('[1] unknown', 0)).toEqual([{ text: '[1] unknown' }]); });
  it('counts overlap by unique chunk ID across the union, including empty results', () => {
    expect(overlap([hit, hit], [{ ...hit, chunk_id: 'b' }, hit])).toEqual({ shared: 1, total: 2 });
    expect(overlap([], [])).toEqual({ shared: 0, total: 0 });
  });
  it('bounds source counts and year ranges before requesting the API', () => {
    for (const value of ['', '0', '51', '2.5', '-1']) expect(validTopK(value)).toBe(false);
    expect(validTopK('50')).toBe(true);
    expect(filterError({ agency: '', type: '', yearMin: '2026', yearMax: '2020' })).toMatch(/Start year/);
    expect(filterError({ agency: '', type: '', yearMin: '1899', yearMax: '' })).toMatch(/1900/);
    expect(apiFilters({ agency: ' FDA ', type: '', yearMin: '2020', yearMax: '' })).toEqual({ source_agency: 'FDA', year_min: 2020 });
  });
  it('caps history at ten and ignores corrupt or wrong-shaped session data', () => {
    saveHistory(Array.from({ length: 13 }, (_, i) => ({ question: String(i), answer: 'answer' })));
    expect(readHistory()).toHaveLength(10); expect(readHistory()[0].question).toBe('0');
    sessionStorage.setItem('docs_copilot_ask_history', '[{"question":3,"answer":"a"},null]'); expect(readHistory()).toEqual([]);
    sessionStorage.setItem('docs_copilot_ask_history', '{bad'); expect(readHistory()).toEqual([]);
  });
});
