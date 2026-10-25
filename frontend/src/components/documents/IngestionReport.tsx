import { Badge, Banner, CopyButton, Disclosure } from '../ui';
import { count, reindexCommand, reportRows, stringList, syncWarning } from '../../domain/documents';
import type { IngestionJob } from '../../domain/documents';
import styles from './documents.module.css';

function Rows({ value, kind }: { value: unknown; kind: string }) {
  const rows = reportRows(value);
  if (!rows.length) return null;
  return <div><h3 className={styles.heading}>{kind}</h3><ul className={styles.list}>{rows.map((row, index) => <li key={index}>{typeof row.filename === 'string' && <strong>{row.filename}: </strong>}{typeof row.row === 'number' && `Row ${row.row}. `}{typeof row.reason === 'string' && row.reason}{stringList(row.reasons).join('; ')}{stringList(row.changed_fields).length > 0 && `Updated ${stringList(row.changed_fields).join(', ')}.`}{stringList(row.metadata_updated).length > 0 && ` Metadata updated: ${stringList(row.metadata_updated).join(', ')}.`}{typeof row.chunks === 'number' && ` ${row.chunks} chunks.`}{typeof row.document_id === 'string' && <div className={styles.hint}>Document {row.document_id}</div>}</li>)}</ul></div>;
}
export default function IngestionReport({ job }: { job: IngestionJob }) {
  const report = job.report;
  const partial = (count(report?.documents_failed) ?? 0) > 0 || reportRows(report?.failures).length > 0 || reportRows(report?.rejected_rows).length > 0;
  const stats = [['documents_ingested', 'Documents ingested'], ['documents_updated', 'Documents replaced'], ['chunks', 'Chunks'], ['documents_duplicate', 'Duplicates'], ['documents_metadata_updated', 'Metadata updates'], ['documents_failed', 'Failed documents']] as const;
  return <div className={styles.stack}>
    {syncWarning(job) && <Banner tone="warning" title="Qdrant needs to be rebuilt"><p className={styles.text}>The job reports that Postgres committed this document, but the Qdrant index is out of date. Ask the operator to rebuild the index before relying on Qdrant results.</p><pre className={styles.code}>{reindexCommand}</pre><CopyButton text={reindexCommand} label="Copy reindex command" /></Banner>}
    {job.error && <Banner tone="danger" title="Ingestion reported an error"><p className={styles.text}>{job.error}</p></Banner>}
    {partial && <Banner tone="warning" title="Some documents need attention">This job includes failed documents or rejected rows. Review the supplied reasons below; a completed job does not mean every row succeeded.</Banner>}
    {report ? <><div className={styles.toolbar}><h3 className={styles.heading}>Ingestion report</h3>{typeof report.duration_ms === 'number' && Number.isFinite(report.duration_ms) && report.duration_ms >= 0 && <Badge>{(report.duration_ms / 1000).toFixed(2)} s reported duration</Badge>}</div><div className={styles.stats}>{stats.map(([key, label]) => { const value = count(report[key]); return value !== null ? <div className={styles.stat} key={key}><strong>{value.toLocaleString()}</strong><span>{label}</span></div> : null; })}</div>
      <Rows value={report.failures} kind="Failed documents" /><Rows value={report.rejected_rows} kind="Rejected rows" />
      <Disclosure title="Document and metadata details"><Rows value={report.documents} kind="Ingested documents" /><Rows value={report.updates} kind="Replaced documents" /><Rows value={report.duplicates} kind="Duplicate documents" /><Rows value={report.metadata_updates} kind="Metadata updates" /></Disclosure>
      <Disclosure title="Full ingestion report"><p className={styles.hint}>Counts and fields absent from the supplied report are unavailable. The original report is preserved below.</p><pre className={styles.code}>{JSON.stringify(report, null, 2)}</pre></Disclosure></> : <Banner title="No ingestion report was supplied">{job.status === 'failed' ? 'Review the job error before trying again.' : 'The job finished without a report. Its document and chunk counts are unavailable.'}</Banner>}
  </div>;
}
