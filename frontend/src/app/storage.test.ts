import { describe, expect, it } from 'vitest';
import { DEFAULTS, KEY_STORAGE, loadKey, loadPreferences, normalizeBaseUrl, saveKey, savePreferences } from './storage';

describe('settings storage', () => {
  it('keeps keys only in session storage and forgets them', () => {
    saveKey('private-test-value'); expect(loadKey()).toBe('private-test-value');
    expect(localStorage.getItem(KEY_STORAGE)).toBeNull(); saveKey(''); expect(sessionStorage.getItem(KEY_STORAGE)).toBeNull();
  });
  it('stores only non-secret preferences and validates persisted defaults', () => {
    savePreferences({ ...DEFAULTS, theme: 'dark', topK: 20 }); expect(loadPreferences().theme).toBe('dark'); expect(loadPreferences().topK).toBe(20);
    localStorage.setItem('docs_copilot_preferences', '{"topK":500,"theme":"invalid","backend":"other"}'); expect(loadPreferences()).toEqual(DEFAULTS);
    localStorage.setItem('docs_copilot_preferences', 'broken'); expect(loadPreferences()).toEqual(DEFAULTS);
  });
  it.each(['https://user:password@api.test', 'https://api.test?key=private', 'https://api.test#secret', 'javascript:alert(1)', '//api.test', '/api?key=value', '/api#secret'])('rejects unsafe address %s', value => { expect(() => normalizeBaseUrl(value)).toThrow(); });
  it('supports same-origin proxies and HTTP addresses', () => { expect(normalizeBaseUrl('/api/')).toBe('/api'); expect(normalizeBaseUrl('http://127.0.0.1:8001/')).toBe('http://127.0.0.1:8001'); });
});
