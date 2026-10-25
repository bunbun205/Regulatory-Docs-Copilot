import { useEffect, useId, useRef, useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { Button, Disclosure, Field, Input, Select } from '../ui';
import { apiFilters, emptyFilters, filterError, validTopK } from '../../domain/research';
import type { Backend, FilterValues } from '../../domain/research';
import styles from './research.module.css';

export function FilterBar({ values, onChange }: { values: FilterValues; onChange: (values: FilterValues) => void }) {
  const [open, setOpen] = useState(false); const id = useId();
  const container = useRef<HTMLDivElement>(null); const opener = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    container.current?.querySelector('input')?.focus();
    const outside = (event: MouseEvent) => { if (!container.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); opener.current?.focus(); } };
    document.addEventListener('mousedown', outside); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('mousedown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  const count = Object.keys(apiFilters(values) ?? {}).length;
  const fields = [{ key: 'agency', label: 'Agency', max: 200 }, { key: 'type', label: 'Document type', max: 100 }, { key: 'yearMin', label: 'Start year', max: 4 }, { key: 'yearMax', label: 'End year', max: 4 }] as const;
  return <div ref={container} className={styles.filter}><button ref={opener} type="button" className={styles.chip} style={{ padding: '8px 12px' }} aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}><SlidersHorizontal size={14} aria-hidden="true" /> Filters{count > 0 ? ` (${count})` : ''}</button>
    {open && <div id={id} role="group" aria-label="Regulation filters" className={styles.popover}><div className={styles.grid}>{fields.map(field => <Field key={field.key} id={`${id}-${field.key}`} label={field.label}><Input id={`${id}-${field.key}`} maxLength={field.max} inputMode={field.key.startsWith('year') ? 'numeric' : undefined} value={values[field.key]} onChange={event => onChange({ ...values, [field.key]: event.target.value })} /></Field>)}</div>{filterError(values) && <p role="alert" className={styles.error}>{filterError(values)}</p>}<div className={styles.actions} style={{ marginTop: 16 }}><Button variant="quiet" onClick={() => onChange(emptyFilters)}>Clear filters</Button><Button variant="secondary" onClick={() => { setOpen(false); opener.current?.focus(); }}>Done</Button></div></div>}
  </div>;
}
export default function ResearchControls({ filters, setFilters, backend, setBackend, topK, setTopK, disabled = false, advanced = true }: { filters: FilterValues; setFilters: (value: FilterValues) => void; backend: Backend; setBackend: (value: Backend) => void; topK: string; setTopK: (value: string) => void; disabled?: boolean; advanced?: boolean }) {
  const id = useId();
  const controls = <div className={styles.grid}><Field id={`${id}-backend`} label="Vector backend"><Select id={`${id}-backend`} value={backend} onChange={event => setBackend(event.target.value as Backend)}><option value="pgvector">pgvector</option><option value="qdrant">Qdrant</option></Select></Field><Field id={`${id}-top-k`} label="Source count" hint="Whole number from 1 to 50." error={!validTopK(topK) ? 'Choose a whole number from 1 to 50.' : undefined}><Input id={`${id}-top-k`} type="number" min="1" max="50" step="1" value={topK} onChange={event => setTopK(event.target.value)} /></Field></div>;
  return <fieldset disabled={disabled} className={styles.controls}><div className={styles.controlRow}><FilterBar values={filters} onChange={setFilters} />{apiFilters(filters) && <span className={styles.hint}>Filters apply to loaded documents.</span>}</div>{advanced ? <Disclosure title="Advanced">{controls}</Disclosure> : <div style={{ marginTop: 16 }}>{controls}</div>}{filterError(filters) && <p role="alert" className={styles.error}>{filterError(filters)}</p>}</fieldset>;
}
