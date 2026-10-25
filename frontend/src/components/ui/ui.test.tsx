import { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/errors';
import { Drawer, ErrorBanner, Tabs } from '.';

describe('shared error UI', () => {
  it('counts down Retry-After before enabling retry', async () => {
    vi.useFakeTimers(); const retry = vi.fn();
    render(<ErrorBanner error={new ApiError(429, 'rate_limited', 'Wait', 'request-1', 2)} baseUrl="/api" onRetry={retry} />);
    expect((screen.getByRole('button', { name: 'Retry in 2s' }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    const button = screen.getByRole('button', { name: 'Retry' }) as HTMLButtonElement;
    expect(button.disabled).toBe(false); fireEvent.click(button); expect(retry).toHaveBeenCalledTimes(1);
  });
  it('renders untrusted messages as text and copies only safe details', async () => {
    const writeText = vi.fn(async (_text: string) => {});
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    const { container } = render(<ErrorBanner error={new ApiError(400, 'bad_request', '<script>untrusted()</script>', 'request-2')} baseUrl="/api" />);
    expect(screen.getByText('<script>untrusted()</script>')).toBeTruthy(); expect(container.querySelector('script')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Copy details' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(JSON.parse(writeText.mock.calls[0][0]).requestId).toBe('request-2');
  });
});

describe('keyboard primitives', () => {
  it('traps focus in the drawer, closes with Escape and returns focus', async () => {
    function Example() { const [open, setOpen] = useState(false); return <><button onClick={() => setOpen(true)}>Open</button><Drawer open={open} title="Sources" onClose={() => setOpen(false)}><button>Last action</button></Drawer></>; }
    const user = userEvent.setup(); render(<Example />);
    const opener = screen.getByRole('button', { name: 'Open' }); await user.click(opener);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close panel' }));
    await user.tab({ shift: true }); expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Last action' }));
    await user.tab(); expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close panel' }));
    await user.keyboard('{Escape}'); expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(opener);
  });
  it('supports arrow-key tab selection', async () => {
    function Example() { const [value, setValue] = useState('one'); return <Tabs label="Input mode" items={[{ value: 'one', label: 'One' }, { value: 'two', label: 'Two' }]} selected={value} onChange={setValue} />; }
    const user = userEvent.setup(); render(<Example />); await user.click(screen.getByRole('tab', { name: 'One' })); await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Two' }).getAttribute('aria-selected')).toBe('true'); expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Two' }));
  });
});
