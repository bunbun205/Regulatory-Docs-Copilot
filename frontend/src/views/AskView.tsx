import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Send } from 'lucide-react';
import { useSettings } from '../app/context';
import { useAsync } from '../hooks/useAsync';
import type { components } from '../types/api';
import { apiFilters, answerMarkdown, emptyFilters, filterError, readHistory, runResult, saveHistory, validTopK } from '../domain/research';
import type { Backend, Run } from '../domain/research';
import { Button, Card, Disclosure, EmptyState, Field, Skeleton } from '../components/ui';
import RequestStatus from '../components/ui/RequestStatus';
import ResearchControls from '../components/research/ResearchControls';
import { AnswerPanel, RunDetails } from '../components/research/Sources';
import styles from '../components/research/research.module.css';

export default function AskView() {
  const { api, preferences } = useSettings();
  const [question, setQuestion] = useState(''); const [filters, setFilters] = useState(emptyFilters);
  const [backend, setBackend] = useState<Backend>(preferences.backend); const [topK, setTopK] = useState(String(preferences.topK));
  const [history, setHistory] = useState(readHistory); const textarea = useRef<HTMLTextAreaElement>(null);
  const action = useAsync<Run<components['schemas']['AskResponse']>>();
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim() || !validTopK(topK) || filterError(filters)) return;
    const query = question.trim();
    void action.run(async signal => {
      const result = await api.request(() => api.client.POST('/v1/ask', { signal, body: { query, top_k: Number(topK), backend, ...(apiFilters(filters) && { filters: apiFilters(filters) }) } }));
      if (result.ok && !signal.aborted) setHistory(previous => { const next = [{ question: query, answer: answerMarkdown(result.data.answer, result.data.insufficient_evidence ? [] : result.data.citations) }, ...previous].slice(0, 10); saveHistory(next); return next; });
      return runResult(result);
    });
  };
  const result = action.data?.payload;
  const edit = (value: string) => { setQuestion(value); textarea.current?.focus(); };
  return <div className={styles.stack}><Card><form className={styles.form} onSubmit={submit}><Field id="ask-question" label="Your question" hint="Ctrl or ⌘ + Enter to ask. Answers are limited to the loaded documents."><textarea ref={textarea} id="ask-question" className={styles.question} aria-describedby="ask-question-hint" maxLength={2000} value={question} onChange={event => { setQuestion(event.target.value); event.target.style.height = 'auto'; event.target.style.height = `${Math.min(440, event.target.scrollHeight)}px`; }} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="What do the loaded regulations say about…" disabled={action.pending} /></Field><ResearchControls filters={filters} setFilters={setFilters} backend={backend} setBackend={setBackend} topK={topK} setTopK={setTopK} disabled={action.pending} /><div className={styles.actions}><Button type="submit" disabled={action.pending || action.retryIn > 0 || !question.trim() || !validTopK(topK) || Boolean(filterError(filters))}><Send size={16} aria-hidden="true" />Ask documents</Button><span className={styles.hint}>A local model can take up to 3 minutes.</span></div></form><RequestStatus action={action} baseUrl={preferences.baseUrl} /></Card>
    {action.pending && <Card><Skeleton lines={5} /></Card>}
    {!result && !action.pending && !action.error && !action.stopped && <EmptyState title="Start with a question">Ask about a procedure, a requirement or a point that needs a closer look. Review the sources alongside each answer.</EmptyState>}
    {result && <AnswerPanel answer={result.answer} citations={result.citations} grounded={result.grounded} insufficient={result.insufficient_evidence} topScore={result.top_score} details={<RunDetails backend={result.backend} usage={result.usage} latency={result.latency_ms} requestId={action.data?.requestId ?? null} reason={result.grounding_reason} />} actions={<><Button variant="secondary" onClick={() => edit(result.query)}>Ask again</Button><Link to={`/search?${new URLSearchParams({ q: result.query }).toString()}`}>Open as search <ArrowRight size={14} aria-hidden="true" /></Link></>} />}
    {history.length > 0 && <Card><Disclosure title={`Session history (${history.length}/10)`}><p className={styles.hint}>Stored in this browser session. Clearing history leaves the current answer on screen.</p><Button variant="quiet" onClick={() => { saveHistory([]); setHistory([]); }}>Clear history</Button>{history.map((item, i) => <div className={styles.history} key={i}><strong>{item.question}</strong><p>{item.answer}</p><Button variant="secondary" disabled={action.pending} onClick={() => edit(item.question)}>Use question {i + 1}</Button></div>)}</Disclosure></Card>}
  </div>;
}
