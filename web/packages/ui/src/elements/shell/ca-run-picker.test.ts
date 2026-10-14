// @vitest-environment happy-dom
// The run picker's options: a stub run carries its mark beside its name.
import type { RunSummary } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import './ca-run-picker.js';
import type { CaRunPicker } from './ca-run-picker.js';

const run = (name: string, extra: Partial<RunSummary> = {}): RunSummary =>
  ({
    run: name, started_at: '2026-10-11T00:00:00', last_ts: '2026-10-11T00:01:05', running: false, quota: [],
    tasks: { total: 1, done: 1, failed: 0, not_started: 0, skipped: 0, running: 0, waiting: 0 }, ...extra,
  }) as unknown as RunSummary;

describe('ca-run-picker', () => {
  it('marks a stub run beside its name, with a tooltip, and no other run', async () => {
    const el: CaRunPicker = document.createElement('ca-run-picker');
    Object.assign(el, { runs: [run('docs-stub', { stub: true }), run('docs')], current: 'docs' });
    document.body.append(el);
    await el.updateComplete;
    const items = [...el.shadowRoot!.querySelectorAll('.item')];
    expect(items[0]!.textContent).toContain('Trends'); // the pages of no run come first
    const names = items.slice(1).map((i) => i.querySelector('.nm')!);
    expect(names.map((n) => n.querySelector('.pill')?.textContent ?? '')).toEqual(['stub agent', '']);
    expect(names[0]!.querySelector('.pill')!.getAttribute('title')).toBe('A run whose tasks the stub agent played with scripted replies, not a model (stub)');
    el.remove();
  });
});
