import { createContext, useContext } from 'react';
import type { Api, ApiResult } from '../api/client';
import type { ApiError } from '../api/errors';
import type { Preferences } from './storage';
import type { components } from '../types/api';

export type Identity = components['schemas']['WhoAmIResponse'];
export type ReadyData = { status: string; checks: Record<string, string> };
type Settings = {
  preferences: Preferences; updatePreferences: (changes: Partial<Preferences>) => void;
  key: string; identity: Identity | null; unauthorized: ApiError | null; api: Api;
  validate: (baseUrl: string, key: string, signal: AbortSignal) => Promise<ApiResult<Identity>>;
  forget: () => void;
  readiness: { data: ReadyData | null; error: ApiError | null; pending: boolean; refresh: () => void };
};
export const SettingsContext = createContext<Settings | null>(null);
export function useSettings() {
  const value = useContext(SettingsContext);
  if (!value) throw new Error('Settings provider is missing');
  return value;
}
