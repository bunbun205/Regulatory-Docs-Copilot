import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import IngestionReport from './IngestionReport';
import { ingestionJob } from '../../test/documents';
import { reindexCommand } from '../../domain/documents';

describe('Ingestion report', () => {
  it('shows partial failures and rejected row reasons even when the job completed', async () => {
    render(<IngestionReport job={ingestionJob} />);
    expect(screen.getByText('Some documents need attention')).toBeTruthy(); expect(screen.getByText('PDF could not be read.', { exact: false, selector: 'li' })).toBeTruthy(); expect(screen.getByText(/Required title is missing/, { selector: 'li' })).toBeTruthy();
    await userEvent.click(screen.getByText('Document and metadata details'));
    expect(screen.getByText(/Updated title/)).toBeTruthy(); expect(screen.getByText(/Metadata updated: title/)).toBeTruthy();
    expect(screen.getByText('Duplicates')).toBeTruthy(); expect(screen.getByText('Chunks')).toBeTruthy();
  });
  it('shows and copies the recovery command only for an explicit post-commit sync failure', async () => {
    const user = userEvent.setup(); const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    render(<IngestionReport job={{ ...ingestionJob, status: 'failed', report: null, error: 'Postgres committed this document, but the qdrant index is out of date.' }} />);
    expect(screen.getByText('Qdrant needs to be rebuilt')).toBeTruthy(); await user.click(screen.getByRole('button', { name: 'Copy reindex command' })); expect(write).toHaveBeenCalledWith(reindexCommand);
  });
  it('renders malicious file names, reasons and unknown report data as text', async () => {
    const hostile = '<img src=x onerror=alert(1)>';
    const { container } = render(<IngestionReport job={{ ...ingestionJob, report: { ...ingestionJob.report, failures: [{ filename: hostile, reason: '<script>bad()</script>' }], extra: '<svg onload=bad()>' } }} />);
    expect(screen.getByText('<script>bad()</script>', { exact: false, selector: 'li' })).toBeTruthy(); await userEvent.click(screen.getByText('Full ingestion report')); expect(container.querySelector('img,script,svg[onload]')).toBeNull(); expect(container.textContent).toContain('<svg onload=bad()>');
  });
  it('omits malformed counts and preserves the original unknown fields in Details', async () => {
    render(<IngestionReport job={{ ...ingestionJob, report: { chunks: '3', documents_ingested: {}, duration_ms: -1, failures: 'wrong', custom: ['opaque'] } }} />);
    expect(screen.queryByText('Chunks')).toBeNull(); expect(screen.queryByText(/reported duration/)).toBeNull(); await userEvent.click(screen.getByText('Full ingestion report')); expect(screen.getByText(/"opaque"/)).toBeTruthy();
  });
  it('explains missing reports instead of implying success', () => {
    render(<IngestionReport job={{ ...ingestionJob, report: null }} />); expect(screen.getByText('No ingestion report was supplied')).toBeTruthy(); expect(screen.getByText(/counts are unavailable/)).toBeTruthy();
  });
});
