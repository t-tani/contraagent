import type { JournalRow, TranscriptEvent } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { applyEvents, emptyTranscript } from './model.js';
import { classifyRounds } from './rounds.js';
import { transcriptSections } from './sections.js';

const FIXUP = 'The output file(s) you wrote do not pass their checks.\nErrors:\n- /runs/r/out/a.json: [three_points] points: exactly 3';
const launch = (prompt: string, truncated = 0): TranscriptEvent => ({
  type: 'launch',
  argv: ['/usr/bin/claude', '-p', '--model', 'claude-sonnet-x'],
  cwd: '/w',
  prompt,
  prompt_truncated: truncated,
});

function sectionsOf(events: TranscriptEvent[], rows: JournalRow[], active = false) {
  const t = emptyTranscript();
  applyEvents(t, events);
  const rounds = classifyRounds(
    t.rounds.map((r) => r.launch),
    rows,
  );
  return transcriptSections(t, rounds, { run: 'r', rows, active });
}

describe('transcriptSections', () => {
  const rows: JournalRow[] = [{ ts: '2026-10-13T00:00:00Z', key: 'k', kind: 'k', stop: 'error', ok: false, attempt: 0, reason: 'tool crashed' }];
  const sections = sectionsOf(
    [
      launch('TELEMETRY run=r role=writer\n\nDo it.', 12),
      { type: 'auto_retry_start', err: '429' },
      { type: 'tool_execution_start', tool: 'Bash', cmd: 'ls', intent: '', call: 'c' },
      launch(FIXUP),
      { type: 'message_update', ev: 'text_delta', delta: 'fixed' },
    ],
    rows,
    true,
  );

  it('names each round as the reader counts them, with how it ended', () => {
    expect(sections.map((s) => [s.title, s.facts, s.verdict, s.active])).toEqual([
      ['Attempt 1', ['sonnet-x'], { tone: 'failed', text: 'failed checks', tip: 'Output failed checks' }, false],
      ['Correction 1', ['sonnet-x'], { tone: 'failed', text: 'failed', tip: 'tool crashed' }, true],
    ]);
    expect(sections[0]?.footer).toEqual({
      tone: 'attention',
      title: 'Output failed checks',
      list: ['out/a.json: [three_points] points: exactly 3'],
      note: 'Sent in the correction prompt',
    });
    expect(sections[1]?.footer).toEqual({ tone: 'failed', title: 'Attempt 1 failed: tool crashed' });
  });

  it('heads a round with who ran it, its command line and its prompt', () => {
    const s = sections[0]!;
    expect(s.tags?.map((t) => [t.label, t.value, t.look])).toEqual([
      ['coding agent', 'Claude Code', undefined],
      ['model', 'claude-sonnet-x', 'mono'],
      ['role', 'writer', 'quiet'],
    ]);
    expect(s.details?.map((d) => [d.id, d.summary, !!d.code])).toEqual([
      ['cmd', 'Command line', true],
      ['prompt', 'Prompt (35 characters; 12 characters not saved)', false],
    ]);
    expect(s.details?.[1]?.text.endsWith('(12 characters not saved)')).toBe(true);
  });

  it('gives the items as the element takes them, an API request sent again titled', () => {
    expect(sections[0]?.items.map((i) => [i.type, 'title' in i ? i.title : ''])).toEqual([
      ['event', 'API request sent again'],
      ['tool', ''],
    ]);
    expect(sections[1]?.items).toEqual([{ type: 'message', id: 'i1', text: 'fixed' }]);
  });
});
