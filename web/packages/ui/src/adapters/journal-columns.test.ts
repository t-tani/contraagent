// @vitest-environment happy-dom
import type { JournalRow } from '@contraagent/api';
import { render } from 'lit';
import { describe, expect, it } from 'vitest';
import { journalColumns } from './journal-columns.js';
import { customValue, customValues } from '../words/row-extras.js';

const row = (key: string, extra: Record<string, unknown> = {}): JournalRow =>
  ({ ts: '2026-10-14T00:00:01', key, kind: 'write', stop: 'completed', ok: true, wall_s: 1, ...extra });

describe('journalColumns', () => {
  it("adds a column per pipeline's own column, after the reason, named as written", () => {
    const rows = [row('write-a', { effect: 'new', lines: 3 }), row('write-b', { effect: { kind: 'merge' } })];
    const ctx = { run: 'r', outcomes: new Map(), journal: rows, rows };
    const plain = journalColumns(ctx);
    const cols = journalColumns({ ...ctx, extras: ['effect', 'lines'] });
    expect(cols.map((c) => c.id)).toEqual([...plain.map((c) => c.id), 'x:effect', 'x:lines']);
    const [effect, lines] = cols.slice(-2);
    expect(effect!.header).toBe('effect');
    expect(effect!.tip).toBe('Custom column (row_extras)');
    expect(rows.map((r) => effect!.text!(r))).toEqual(['new', '{"kind":"merge"}']);
    expect(rows.map((r) => lines!.text!(r))).toEqual(['3', '—']);
  });

  it("counts an attempt's safety stops in its reason, each stop's facts in the tooltip", () => {
    const rows = [row('write-a', { safety_stops: [{ part: 'tool', model: 'haiku', tool: 'WebFetch' }, { part: 'unread' }] }), row('write-b')];
    const reason = journalColumns({ run: 'r', outcomes: new Map(), journal: rows, rows }).find((c) => c.id === 'reason')!;
    const cell = (r: JournalRow) => {
      const box = document.createElement('div');
      render(reason.cell(r, 0), box);
      return box;
    };
    const mark = cell(rows[0]!).querySelector('[data-tone="attention"]');
    expect(mark!.textContent.trim()).toBe('2 safety stops');
    expect(mark!.getAttribute('title')).toBe(
      'A safety classifier stopped part of the agent session, and the session went on (safety_stops)\ntool request | haiku | WebFetch\nunrecognized',
    );
    expect(cell(rows[1]!).textContent).not.toContain('safety');
  });
});

describe('customValue', () => {
  it('keeps text, writes numbers and booleans, and anything else as compact JSON', () => {
    expect([customValue('new'), customValue(0), customValue(false), customValue([1, 'a']), customValue(null), customValue('')]).toEqual([
      'new',
      '0',
      'false',
      '[1,"a"]',
      '—',
      '—',
    ]);
    expect(customValues({ a: 1, b: null, c: 'x' }, ['a', 'b', 'c', 'd'])).toEqual([
      ['a', '1'],
      ['c', 'x'],
    ]);
  });
});
