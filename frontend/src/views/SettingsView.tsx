import { useState } from 'react';
import { AlertCircle, Check, CheckCircle2, Database, Eye, EyeOff, KeyRound, Monitor, Moon, Settings2, ShieldCheck, Sun } from 'lucide-react';
import { useSettings } from '../app/context';
import { normalizeBaseUrl } from '../app/storage';
import { useAsync } from '../hooks/useAsync';
import type { Identity } from '../app/context';
import { Badge, Banner, Button, Card, Disclosure, ElapsedTimer, ErrorBanner, Field, IconButton, Input, Select, Skeleton, Spinner } from '../components/ui';
import styles from './SettingsView.module.css';

export default function SettingsView() {
  const { key, preferences, identity, unauthorized, validate, forget, readiness, updatePreferences } = useSettings();
  const [draftKey, setDraftKey] = useState(key);
  const [baseUrl, setBaseUrl] = useState(preferences.baseUrl);
  const [show, setShow] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [topK, setTopK] = useState(String(preferences.topK));
  const [saved, setSaved] = useState(false);
  const validation = useAsync<Identity>();
  const error = validation.error || unauthorized;
  const write = identity?.scopes.includes('write');
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const next: Record<string, string> = {};
    try { normalizeBaseUrl(baseUrl); } catch (cause) { next.base = cause instanceof Error ? cause.message : 'Check the address.'; }
    if (!draftKey.trim()) next.key = 'Enter an API key to validate.';
    if (draftKey.trim() && baseUrl.includes(draftKey.trim())) next.base = 'Keep your API key out of the address. Enter it only in the key field.';
    setFields(next);
    if (Object.keys(next).length) return;
    void validation.run(signal => validate(baseUrl, draftKey, signal));
  };
  const forgetKey = () => { validation.clear(); forget(); setDraftKey(''); setShow(false); };
  const saveDefaults = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = Number(topK);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 50) { setFields(current => ({ ...current, topK: 'Choose a whole number from 1 to 50.' })); return; }
    setFields(current => ({ ...current, topK: '' })); updatePreferences({ topK: parsed }); setSaved(true);
  };
  return <div className={styles.layout}>
    <div className={styles.primary}>
      <Card>
        <div className={styles.cardHeading}><KeyRound size={19} aria-hidden="true" /><div><h2>API connection</h2><p>Your key connects this tab to your document library.</p></div></div>
        <form onSubmit={submit} className={styles.form}>
          <Field id="api-base" label="API base URL" hint="Use /api for the native local proxy." error={fields.base}><Input id="api-base" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} disabled={validation.pending} aria-invalid={Boolean(fields.base)} aria-describedby={fields.base ? 'api-base-error' : 'api-base-hint'} spellCheck={false} /></Field>
          <Field id="api-key" label="API key" hint="Saved in session storage only. Close the browser session to clear it." error={fields.key}><div className={styles.secretField}><Input id="api-key" type={show ? 'text' : 'password'} value={draftKey} onChange={event => setDraftKey(event.target.value)} autoComplete="off" spellCheck={false} disabled={validation.pending} aria-invalid={Boolean(fields.key)} aria-describedby={fields.key ? 'api-key-error' : 'api-key-hint'} /><IconButton label={show ? 'Hide API key' : 'Show API key'} onClick={() => setShow(value => !value)}>{show ? <EyeOff size={17} /> : <Eye size={17} />}</IconButton></div></Field>
          <div className={styles.actions}><Button type="submit" disabled={validation.pending || validation.retryIn > 0}>{validation.pending ? <Spinner /> : <ShieldCheck size={16} />}{validation.pending ? 'Validating…' : 'Validate key'}</Button><Button variant="quiet" onClick={forgetKey} disabled={!key && !draftKey}>Forget key</Button>{validation.pending && <><ElapsedTimer startedAt={validation.startedAt} /><Button variant="quiet" onClick={validation.stop}>Stop waiting</Button></>}</div>
        </form>
        {error && <div className={styles.feedback}><ErrorBanner error={error} baseUrl={preferences.baseUrl} onRetry={validation.error ? validation.retry : undefined} /></div>}
        {!error && identity && <div className={styles.feedback}><Banner tone={write ? 'success' : 'info'} title={write ? 'Connection verified' : 'Read-only key'}><p>Connected as <strong>{identity.name}</strong>.</p><p>{write ? 'You can read documents and upload new ones.' : 'You can search, ask questions and run gap checks. Uploading documents needs a write key.'}</p></Banner></div>}
        <Disclosure title="About this connection"><p>This browser key-entry flow is intended for a local demo. Shared production deployments should use a dedicated sign-in flow.</p><p>Other API addresses must allow browser access from this origin. A same-origin proxy avoids CORS issues. Credentials are sent only in the API key header.</p></Disclosure>
      </Card>
      <Card>
        <div className={styles.cardHeading}><Settings2 size={19} aria-hidden="true" /><div><h2>Workspace defaults</h2><p>Preferences are saved between visits. Keys last for this session.</p></div></div>
        <form onSubmit={saveDefaults} className={styles.form}>
          <div className={styles.defaultGrid}><Field id="backend" label="Preferred backend"><Select id="backend" value={preferences.backend} onChange={event => updatePreferences({ backend: event.target.value === 'qdrant' ? 'qdrant' : 'pgvector' })}><option value="pgvector">PostgreSQL · pgvector</option><option value="qdrant">Qdrant</option></Select></Field><Field id="top-k" label="Default source count" hint="Between 1 and 50 sources." error={fields.topK}><Input id="top-k" type="number" min={1} max={50} value={topK} onChange={event => { setTopK(event.target.value); setSaved(false); }} aria-describedby={fields.topK ? 'top-k-error' : 'top-k-hint'} aria-invalid={Boolean(fields.topK)} /></Field></div>
          <div className={styles.actions}><Button variant="secondary" type="submit">Save defaults</Button>{saved && <span className={styles.saved} role="status"><Check size={14} />Defaults saved</span>}</div>
        </form>
        <div className={styles.appearance}><span>Appearance</span><div className={styles.themeButtons} role="group" aria-label="Appearance">{([{ value: 'system', label: 'System', Icon: Monitor }, { value: 'light', label: 'Light', Icon: Sun }, { value: 'dark', label: 'Dark', Icon: Moon }] as const).map(({ value, label, Icon }) => <button type="button" key={value} aria-pressed={preferences.theme === value} onClick={() => updatePreferences({ theme: value })}><Icon size={15} aria-hidden="true" />{label}</button>)}</div></div>
      </Card>
    </div>
    <aside className={styles.aside} aria-label="Connection information">
      <Card><div className={styles.cardHeading}><Database size={19} aria-hidden="true" /><div><h2>Service status</h2><p>Checked against your API.</p></div></div>{readiness.pending ? <Skeleton lines={2} /> : <><div className={styles.serviceRows}>{Object.entries(readiness.data?.checks ?? {}).map(([name, status]) => <div key={name}><span>{name === 'database' ? 'PostgreSQL' : name === 'qdrant' ? 'Qdrant' : name.replaceAll('_', ' ')}</span><Badge tone={status === 'ok' ? 'success' : 'warning'}>{status === 'ok' ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}{status === 'ok' ? 'Ready' : status}</Badge></div>)}</div>{readiness.error && <ErrorBanner error={readiness.error} baseUrl={preferences.baseUrl} onRetry={readiness.refresh} />}<p className={styles.note}>The first query may take longer while the embedding model loads.</p></>}<Button variant="quiet" onClick={readiness.refresh}>Refresh status</Button></Card>
      <Card><div className={styles.cardHeading}><ShieldCheck size={19} aria-hidden="true" /><div><h2>Your access</h2><p>Granted by the validated key.</p></div></div>{identity ? <><div className={styles.accessName}>{identity.name}</div><Badge tone={write ? 'success' : 'info'}><KeyRound size={12} />{write ? 'Read & write' : 'Read only'}</Badge><ul className={styles.permissions}><li><Check size={14} />Search & read documents</li><li><Check size={14} />Ask & run analyses</li><li className={!write ? styles.muted : ''}>{write ? <Check size={14} /> : <span aria-hidden="true">—</span>}{write ? 'Upload documents' : 'Uploads require write access'}</li></ul></> : <p className={styles.note}>Validate a key to see its name and effective permissions.</p>}</Card>
    </aside>
  </div>;
}
