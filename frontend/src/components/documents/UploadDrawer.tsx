import { useState } from 'react';
import { Upload } from 'lucide-react';
import { useSettings } from '../../app/context';
import { multipart } from '../../api/contracts';
import { documentFileError, metadataErrors } from '../../domain/documents';
import type { UploadMetadata } from '../../domain/documents';
import { useAsync } from '../../hooks/useAsync';
import type { components } from '../../types/api';
import { Banner, Button, Drawer, Field, Input } from '../ui';
import RequestStatus from '../ui/RequestStatus';
import styles from './documents.module.css';

export default function UploadDrawer({ open, onClose, onAccepted, running }: { open: boolean; onClose: () => void; onAccepted: (id: string) => void; running: boolean }) {
  const { api, preferences } = useSettings();
  const [file, setFile] = useState<File | null>(null);
  const [values, setValues] = useState<UploadMetadata>(() => ({ title: '', source_agency: '', doc_type: 'guidance', year: String(new Date().getFullYear()), version: 'v1' }));
  const [attempted, setAttempted] = useState(false);
  const [selectionError, setSelectionError] = useState('');
  const upload = useAsync<components['schemas']['UploadResponse']>();
  const errors = metadataErrors(values); const fileError = selectionError || documentFileError(file); const disabled = upload.pending || running;
  function choose(chosen: File | null) { setFile(chosen); setSelectionError(''); setAttempted(false); }
  function submit(event: React.FormEvent) {
    event.preventDefault(); setAttempted(true);
    if (!file || fileError || Object.keys(errors).length || disabled) return;
    const selected = file;
    void upload.run(async signal => {
      const result = await api.request(() => api.client.POST('/v1/documents', { signal, body: { file: selected.name, title: values.title.trim(), source_agency: values.source_agency.trim(), doc_type: values.doc_type.trim(), year: Number(values.year), version: values.version.trim() }, bodySerializer: body => multipart(body, selected) }));
      if (result.ok && !signal.aborted) { onAccepted(result.data.job_id); onClose(); }
      return result;
    });
  }
  const fields = [['title', 'Title', 500], ['source_agency', 'Source agency', 200], ['doc_type', 'Document type', 100], ['year', 'Year', 4], ['version', 'Version', 200]] as const;
  return <Drawer open={open} title="Upload a document" onClose={onClose}><form className={styles.drawer} onSubmit={submit} noValidate>
    <p className={styles.hint}>Add one PDF, Markdown or TXT document. The default file limit is 25 MiB; the server applies its configured limit.</p>
    <fieldset disabled={disabled} className={styles.drawer} style={{ border: 0, padding: 0, margin: 0 }}>
      <div className={styles.drop} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (!disabled) { const files = event.dataTransfer.files; if (files.length > 1) { setFile(null); setSelectionError('Choose one document at a time.'); setAttempted(false); } else { const input = event.currentTarget.querySelector<HTMLInputElement>('input[type=file]'); if (input) input.files = files; choose(files[0] ?? null); } } }}><Upload size={24} aria-hidden="true" /><strong>Drop one document here</strong><label htmlFor="upload-file">Or choose a file</label><input id="upload-file" type="file" accept=".pdf,.md,.markdown,.txt" aria-describedby="upload-file-help" aria-invalid={Boolean(fileError && (file || attempted || selectionError))} onChange={event => choose(event.target.files?.[0] ?? null)} /><p className={styles.hint} id="upload-file-help">{file ? `${file.name} · ${file.size.toLocaleString()} bytes selected` : 'One document per upload.'}</p>{fileError && (file || attempted || selectionError) && <Banner tone="danger">{fileError}</Banner>}</div>
      <div className={styles.grid}>{fields.map(([key, label, max]) => <div key={key} className={key === 'title' ? styles.full : undefined}><Field id={`upload-${key}`} label={label} error={attempted ? errors[key] : undefined} hint={key === 'doc_type' ? 'Use the document type recorded by your library, such as guidance or regulation.' : undefined}><Input id={`upload-${key}`} maxLength={max} inputMode={key === 'year' ? 'numeric' : undefined} value={values[key]} aria-invalid={attempted && Boolean(errors[key])} aria-describedby={attempted && errors[key] ? `upload-${key}-error` : undefined} onChange={event => setValues(previous => ({ ...previous, [key]: event.target.value }))} /></Field></div>)}</div>
      <Button type="submit" disabled={disabled || upload.retryIn > 0}><Upload size={16} aria-hidden="true" />{upload.pending ? 'Sending document…' : 'Start upload'}</Button>
    </fieldset>
    <RequestStatus action={upload} baseUrl={preferences.baseUrl} canStop={false} />
    {running && <Banner>Another document is still being ingested. Its status is shown in the library.</Banner>}
  </form></Drawer>;
}
