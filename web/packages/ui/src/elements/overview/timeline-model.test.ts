import type { JournalRow } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { barBox, timeline } from './timeline-model.js';

const row = (key: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T10:00:00Z', key, kind: 'k', stop: 'completed', ok: true, ...extra,
});

describe('timeline', () => {
  const end = Date.parse('2026-10-11T10:00:00Z');

  it('lays finished tasks on lanes by kind, in order of first start', () => {
    const tl = timeline(
      [row('a', { kind: 'late', wall_s: 10 }), row('b', { kind: 'early', wall_s: 60, executor: 'python' }), row('c', { kind: 'late', stop: 'error', ok: false })],
      [],
      end + 1000,
    );
    expect(tl?.lanes.map((l) => [l.name, l.llm, l.bars.map((b) => b.cls)])).toEqual([
      ['early', false, ['py']],
      ['late', true, ['llm', 'bad']],
    ]);
    expect(tl?.t0).toBe(end - 60e3);
    expect(tl?.span).toBe(60e3);
    expect(tl?.live).toBe(false);
  });

  it('leaves out what ended more than six hours before the newest', () => {
    const tl = timeline([row('old', { ts: '2026-10-11T03:00:00Z' }), row('new')], [], end);
    expect(tl?.hidden).toBe(1);
  });

  it('grows running tasks to now, on a span rounded up to the minute', () => {
    const tl = timeline([], [{ kind: 'k', cls: 'llm', t0: end }], end + 30e3);
    expect(tl?.span).toBe(60e3);
    const bar = tl?.lanes[0]?.bars[0];
    expect(bar && tl && barBox(bar, tl, end + 30e3)).toEqual({ left: 0, width: 50 });
    expect(tl?.lanes[0]?.llm).toBe(true);
  });

  it('stacks overlapping bars of one lane on tracks, and greys a task that never started', () => {
    const tl = timeline(
      [row('a', { wall_s: 10 }), row('a', { wall_s: 5, attempt: 1 }), row('z', { stop: 'invalid_input', ok: false, ts: '2026-10-11T10:00:20Z' })],
      [],
      end,
    );
    const lane = tl?.lanes[0];
    expect(lane?.tracks).toBe(2);
    expect(lane?.bars.map((b) => [b.cls, b.track])).toEqual([['llm', 0], ['llm', 1], ['idle', 0]]);
  });

  it('is null with nothing to draw', () => {
    expect(timeline([], [], end)).toBeNull();
  });
});
