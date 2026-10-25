import { useCallback, useId, useState } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle2, FileText } from 'lucide-react';
import { useSettings } from '../../app/context';
import { usePolling } from '../../hooks/usePolling';
import { answerMarkdown, citationParts } from '../../domain/research';
import type { Citation, SearchHit } from '../../domain/research';
import type { components } from '../../types/api';
import { Badge, Banner, Card, CopyButton, Disclosure, Drawer, ErrorBanner, Skeleton } from '../ui';
import styles from './research.module.css';

const terminal = () => true;
export function ScoreBar({ score }: { score: number }) {
  const bounded = Math.min(1, Math.max(-1, score));
  return <div className={styles.score}><div className={styles.scoreLabel}><span>Relevance</span><span>{score.toFixed(3)}</span></div><div className={styles.scoreTrack} role="meter" aria-label="Cosine relevance, not confidence" aria-valuemin={-1} aria-valuemax={1} aria-valuenow={bounded}><span className={styles.scoreFill} style={{ width: `${(bounded + 1) * 50}%` }} /></div></div>;
}
export function CitationChip({ number, citation, onOpen }: { number: number; citation: Citation; onOpen: (citation: Citation) => void }) {
  return <button type="button" className={styles.chip} aria-label={`Source ${number}: ${citation.title}`} onClick={() => onOpen(citation)}>{number}</button>;
}
export function CitedText({ answer, citations, onOpen }: { answer: string; citations: Citation[]; onOpen: (citation: Citation) => void }) {
  return <p className={styles.answer}>{citationParts(answer, citations.length).map((part, i) => 'text' in part ? part.text : <CitationChip key={i} number={part.citation} citation={citations[part.citation - 1]} onOpen={onOpen} />)}</p>;
}
export function CitationStatus({ grounded, insufficient = false, topScore }: { grounded: boolean; insufficient?: boolean; topScore?: number | null }) {
  const [explain, setExplain] = useState(false); const id = useId();
  const explanation = 'Every cited source exists in the retrieved set. This does not prove the source supports the claim. Read the sources.';
  if (insufficient) return <Banner tone="info" title="Not enough evidence">The loaded documents did not provide enough relevant evidence. Try a narrower question or adjust the filters.{topScore !== null && topScore !== undefined && <ScoreBar score={topScore} />}</Banner>;
  if (!grounded) return <Banner tone="warning" title="Sources need review">This answer does not have checked source citations. Review the excerpts carefully before relying on it.</Banner>;
  return <div><button type="button" className={styles.checked} title={explanation} aria-expanded={explain} aria-describedby={explain ? id : undefined} onClick={() => setExplain(value => !value)}><CheckCircle2 size={14} aria-hidden="true" />Citations checked</button>{explain && <p id={id} className={styles.explanation}>{explanation}</p>}</div>;
}
export function SourceDrawer({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const { api, preferences } = useSettings();
  const documentId = citation?.document_id;
  const load = useCallback((signal: AbortSignal) => api.request(() => api.client.GET('/v1/documents/{document_id}', { signal, params: { path: { document_id: documentId ?? '' } } })), [api, documentId]);
  const metadata = usePolling(load, Boolean(documentId), 2000, terminal);
  return <Drawer open={Boolean(citation)} title="Source excerpt" onClose={onClose}>{citation && <div className={styles.stack}><div><p className={styles.hint}>CITED SOURCE</p><h3 className={styles.drawerTitle}>{citation.title}</h3><div className={styles.metadata}>{citation.page !== null && <span>Page {citation.page}</span>}{metadata.data && <><span>{metadata.data.source_agency}</span><span>{metadata.data.year}</span><span>{metadata.data.version}</span></>}</div><ScoreBar score={citation.score} /><p className={styles.hint}>Cosine similarity from −1 to 1; this is relevance, not confidence.</p></div><div><h3 className={styles.subheading}>Excerpt</h3><blockquote className={styles.excerpt}>{citation.snippet}</blockquote><p className={styles.hint} style={{ marginTop: 12 }}>This is the excerpt supplied by the API. It may not contain the full supporting passage.</p></div>{metadata.pending && <Skeleton lines={2} />}{metadata.error && <ErrorBanner error={metadata.error} baseUrl={preferences.baseUrl} onRetry={metadata.refresh} />}<CopyButton text={`${citation.title}${citation.page !== null ? `, page ${citation.page}` : ''}\n${citation.snippet}`} label="Copy excerpt" /><Disclosure title="Source details"><dl className={styles.details}><dt>Document ID</dt><dd>{citation.document_id}</dd><dt>Chunk ID</dt><dd>{citation.chunk_id}</dd>{!metadata.data && <><dt>Document metadata</dt><dd>Unavailable until the document details can be loaded.</dd></>}</dl></Disclosure></div>}</Drawer>;
}
export function SourceCard({ hit }: { hit: SearchHit }) {
  return <Card><h3 className={styles.subheading}><FileText size={14} aria-hidden="true" /> {hit.title}</h3><div className={styles.metadata}><span>{hit.source_agency}</span><span>{hit.doc_type}</span><span>{hit.year}</span>{hit.version && <span>{hit.version}</span>}{hit.page !== null && <span>Page {hit.page}</span>}{hit.section_heading && <span>{hit.section_heading}</span>}</div><ScoreBar score={hit.score} /><h4 className={styles.subheading}>Excerpt</h4><p className={styles.excerpt}>{hit.text}</p></Card>;
}
export function RunDetails({ backend, usage, latency, requestId, reason }: { backend: string; usage: components['schemas']['AskUsage']; latency: number | components['schemas']['AskLatency']; requestId: string | null; reason: string | null }) {
  return <dl className={styles.details}><dt>Backend</dt><dd>{backend}</dd>{typeof latency === 'number' ? <><dt>Total time</dt><dd>{(latency / 1000).toFixed(2)} s</dd></> : <><dt>Retrieval</dt><dd>{(latency.retrieve_ms / 1000).toFixed(2)} s</dd><dt>Generation</dt><dd>{(latency.generate_ms / 1000).toFixed(2)} s</dd></>}<dt>Tokens in / out / total</dt><dd>{usage.input_tokens} / {usage.output_tokens} / {usage.total_tokens}</dd><dt>Request ID</dt><dd>{requestId ?? 'Unavailable'}</dd><dt>Model / provider</dt><dd>Unavailable in this API response.</dd>{reason && <><dt>Citation check reason</dt><dd>{reason}</dd></>}</dl>;
}
export function AnswerPanel({ answer, citations, grounded, insufficient = false, topScore, details, actions }: { answer: string; citations: Citation[]; grounded: boolean; insufficient?: boolean; topScore?: number | null; details: ReactNode; actions?: ReactNode }) {
  const [selected, setSelected] = useState<Citation | null>(null);
  const sources = insufficient ? [] : citations;
  return <><Card><div className={styles.status}><CitationStatus grounded={grounded} insufficient={insufficient} topScore={topScore} /><Badge>{sources.length} {sources.length === 1 ? 'source' : 'sources'}</Badge></div><h2 className={styles.heading}>Answer</h2>{answer ? <CitedText answer={answer} citations={sources} onOpen={setSelected} /> : <p>No answer text was returned. Review the run status and details.</p>}{sources.length > 0 && <div><h3 className={styles.subheading}>Sources</h3><p className={styles.hint} style={{ marginBottom: 12 }}>Review the excerpts alongside the answer. Numbers refer to the sources below.</p><ol className={styles.sources}>{sources.map((citation, i) => <li key={`${citation.chunk_id}:${i}`}><button type="button" className={styles.sourceButton} onClick={() => setSelected(citation)} aria-label={`Read source ${i + 1}: ${citation.title}`}><span className={styles.chip} aria-hidden="true">{i + 1}</span><span>{citation.title}<small>{citation.page !== null ? `Page ${citation.page} · ` : ''}Excerpt · relevance {citation.score.toFixed(3)}</small></span></button></li>)}</ol></div>}<div className={styles.actions} style={{ marginTop: 24 }}><CopyButton text={answerMarkdown(answer, sources)} label="Copy answer & sources" />{actions}</div><Disclosure title="Details">{details}</Disclosure></Card><SourceDrawer citation={selected} onClose={() => setSelected(null)} /></>;
}
