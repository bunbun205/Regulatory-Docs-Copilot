import { useEffect, useId, useRef, useState } from 'react';
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, Check, CheckCircle2, ChevronDown, Copy, FileText, Info, LoaderCircle, X } from 'lucide-react';
import { ApiError, errorDetails, errorMessage } from '../../api/errors';
import styles from './ui.module.css';

export function Button({ variant = 'primary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' | 'danger' }) {
  return <button type="button" className={`${styles.button} ${styles[variant]} ${className}`} {...props} />;
}
export function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <Button variant="quiet" aria-label={label} title={label} className={styles.iconButton} {...props}>{children}</Button>;
}
export function Field({ label, hint, error, id, children }: { label: string; hint?: string; error?: string; id: string; children: ReactNode }) {
  return <div className={styles.field}><label htmlFor={id}>{label}</label>{children}{hint && <p id={`${id}-hint`} className={styles.hint}>{hint}</p>}{error && <p id={`${id}-error`} className={styles.fieldError} role="alert">{error}</p>}</div>;
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) { return <input className={styles.input} {...props} />; }
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) { return <select className={styles.input} {...props} />; }
export function Badge({ tone = 'neutral', children }: { tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'; children: ReactNode }) { return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>; }
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) { return <section className={`${styles.card} ${className}`}>{children}</section>; }
export function Banner({ tone = 'info', title, children, role }: { tone?: 'info' | 'success' | 'warning' | 'danger'; title?: string; children: ReactNode; role?: 'alert' | 'status' }) {
  const Icon = tone === 'danger' || tone === 'warning' ? AlertCircle : tone === 'success' ? CheckCircle2 : Info;
  return <div className={`${styles.banner} ${styles[tone]}`} role={role ?? (tone === 'danger' ? 'alert' : 'status')}><Icon size={18} aria-hidden="true" /><div>{title && <strong>{title}</strong>}<div>{children}</div></div></div>;
}
export function Disclosure({ title, children }: { title: string; children: ReactNode }) { return <details className={styles.disclosure}><summary>{title}<ChevronDown size={16} aria-hidden="true" /></summary><div>{children}</div></details>; }
export function Spinner() { return <LoaderCircle size={18} className={styles.spinner} aria-hidden="true" />; }
export function ElapsedTimer({ startedAt }: { startedAt: number | null }) {
  const [seconds, setSeconds] = useState(() => startedAt === null ? 0 : Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
  useEffect(() => {
    if (startedAt === null) return;
    const timer = setInterval(() => setSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000))), 1000);
    return () => clearInterval(timer);
  }, [startedAt]);
  return <span className={styles.elapsed} aria-label="Elapsed time">{startedAt === null ? 0 : seconds}s elapsed</span>;
}
export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [status, setStatus] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setStatus('Copied'); }
    catch { setStatus('Copy failed. Select the details to copy manually.'); }
    clearTimeout(timer.current); timer.current = setTimeout(() => setStatus(''), 3000);
  };
  return <span className={styles.copy}><Button variant="quiet" onClick={() => { void copy(); }}>{status === 'Copied' ? <Check size={14} /> : <Copy size={14} />}{label}</Button><span role="status" className={styles.hint}>{status}</span></span>;
}
export function ErrorBanner({ error, baseUrl, onRetry }: { error: ApiError; baseUrl: string; onRetry?: () => void }) {
  return <ErrorBody key={`${error.status}:${error.requestId}:${error.occurredAt}`} error={error} baseUrl={baseUrl} onRetry={onRetry} />;
}
function ErrorBody({ error, baseUrl, onRetry }: { error: ApiError; baseUrl: string; onRetry?: () => void }) {
  const [until] = useState(() => Date.now() + (error.retryAfter ?? 0) * 1000);
  const [remaining, setRemaining] = useState(error.retryAfter ?? 0);
  useEffect(() => {
    if (!error.retryAfter) return;
    const timer = setInterval(() => { const value = Math.max(0, Math.ceil((until - Date.now()) / 1000)); setRemaining(value); if (value === 0) clearInterval(timer); }, 250);
    return () => clearInterval(timer);
  }, [error.retryAfter, until]);
  return <Banner tone="danger" title="Something needs your attention"><p>{errorMessage(error, baseUrl)}</p>{remaining > 0 && <p role="status">Try again in {remaining}s.</p>}<div className={styles.actions}>{onRetry && <Button variant="secondary" onClick={onRetry} disabled={remaining > 0}>Retry{remaining > 0 ? ` in ${remaining}s` : ''}</Button>}<CopyButton text={errorDetails(error)} label="Copy details" /></div><Disclosure title="Details"><pre>{errorDetails(error)}</pre></Disclosure></Banner>;
}
export function EmptyState({ title, children }: { title: string; children: ReactNode }) { return <div className={styles.empty}><FileText size={28} strokeWidth={1.3} aria-hidden="true" /><h2>{title}</h2><p>{children}</p></div>; }
export function Skeleton({ lines = 3 }: { lines?: number }) { return <div className={styles.skeleton} role="status" aria-label="Loading"><span className={styles.srOnly}>Loading…</span>{Array.from({ length: lines }, (_, i) => <span key={i} />)}</div>; }
export function Stat({ label, value }: { label: string; value: ReactNode }) { return <div className={styles.stat}><strong>{value}</strong><span>{label}</span></div>; }
export function Toast({ children }: { children: ReactNode }) { return <div className={styles.toast} role="status">{children}</div>; }
export function Tabs({ label, items, selected, onChange }: { label: string; items: { value: string; label: string }[]; selected: string; onChange: (value: string) => void }) {
  return <div role="tablist" aria-label={label} className={styles.tabs}>{items.map((item, index) => <button type="button" role="tab" aria-selected={selected === item.value} tabIndex={selected === item.value ? 0 : -1} key={item.value} onClick={() => onChange(item.value)} onKeyDown={event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
    onChange(items[next].value); const tab = event.currentTarget.parentElement?.children[next]; if (tab instanceof HTMLElement) tab.focus();
  }}>{item.label}</button>)}</div>;
}
export function Drawer({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const id = useId();
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const root = document.getElementById('root');
    const wasInert = root?.inert;
    if (root) root.inert = true;
    const elements = () => Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]') ?? []).filter(element => !element.hidden);
    elements()[0]?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); close.current(); }
      if (event.key === 'Tab') {
        const items = elements(); const first = items[0]; const last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener('keydown', keydown);
    const overflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', keydown); document.body.style.overflow = overflow; if (root) root.inert = wasInert ?? false; previous?.focus(); };
  }, [open]);
  if (!open) return null;
  return createPortal(<div className={styles.backdrop} onClick={event => { if (event.target === event.currentTarget) onClose(); }}><div ref={panel} className={styles.drawer} role="dialog" aria-modal="true" aria-labelledby={id}><div className={styles.drawerHeader}><h2 id={id}>{title}</h2><IconButton label="Close panel" onClick={onClose}><X size={20} /></IconButton></div>{children}</div></div>, document.body);
}
