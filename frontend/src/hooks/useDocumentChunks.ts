import { useEffect, useMemo, useState } from 'react';
import { useSettings } from '../app/context';
import type { Document } from '../domain/documents';

type Counts = Record<string, number | 'error'>;
export default function useDocumentChunks(documents: Document[], revision: number) {
  const { api } = useSettings();
  const cache = useMemo(() => ({ api, revision, counts: new Map<string, number>() }), [api, revision]);
  const [state, setState] = useState<{ cache: typeof cache; values: Counts }>({ cache, values: {} });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); let cursor = 0;
    const values: Counts = {};
    for (const document of documents) { const value = cache.counts.get(document.id); if (value !== undefined) values[document.id] = value; }
    async function worker() {
      while (!controller.signal.aborted && cursor < documents.length) {
        const document = documents[cursor++]; if (cache.counts.has(document.id)) continue;
        const result = await api.request(() => api.client.GET('/v1/documents/{document_id}', { params: { path: { document_id: document.id } }, signal: controller.signal }));
        if (controller.signal.aborted) return;
        if (result.ok) {
          // Bound the per-view cache as well as request concurrency.
          if (cache.counts.size >= 200) { const first = cache.counts.keys().next().value; if (first !== undefined) cache.counts.delete(first); }
          cache.counts.set(document.id, result.data.chunk_count); values[document.id] = result.data.chunk_count;
        } else values[document.id] = 'error';
        setState({ cache, values: { ...values } });
      }
    }
    void Promise.resolve().then(async () => {
      if (controller.signal.aborted) return;
      setState({ cache, values: { ...values } });
      await Promise.all(Array.from({ length: Math.min(3, documents.length) }, worker));
    });
    return () => controller.abort();
  }, [api, cache, documents, retry]);
  return { values: state.cache === cache ? state.values : {}, retry: () => setRetry(value => value + 1) };
}
