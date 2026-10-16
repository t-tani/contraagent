// @vitest-environment happy-dom
// A saved transcript given again with more events is the same transcript grown:
// its new events are drawn below what is there, which stays (no new element, no
// rows drawn again). Another transcript starts over.
import type { TranscriptEvent } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import './ca-transcript.js';
import type { CaTranscript } from './ca-transcript.js';

const launch = (ts: number): TranscriptEvent => ({ type: 'launch', ts, argv: ['claude', '-p'], cwd: '/w', prompt: 'do it' });
const say = (delta: string): TranscriptEvent => ({ type: 'message_update', ev: 'text_delta', delta });
const tool = (call: string, cmd: string): TranscriptEvent => ({ type: 'tool_execution_start', tool: 'read', cmd, intent: '', call });

async function mount(events: TranscriptEvent[]) {
  const el = document.createElement('ca-transcript');
  el.events = events;
  document.body.append(el);
  await settle(el);
  return el;
}

const settle = async (el: CaTranscript) => {
  await el.updateComplete;
  const inner = el.shadowRoot!.querySelector('cae-transcript');
  await (inner as unknown as { updateComplete?: Promise<unknown> } | null)?.updateComplete;
};

const inner = (el: CaTranscript) => el.shadowRoot!.querySelector('cae-transcript')!;
const cards = (el: CaTranscript) => [...inner(el).shadowRoot!.querySelectorAll('[data-card]')];

describe('ca-transcript', () => {
  it('appends the new events of a grown saved transcript, keeping what is drawn', async () => {
    const all = [launch(1), say('Reading the call file.'), tool('c1', '/w/call.json'), tool('c2', '/w/in.md')];
    const el = await mount(all.slice(0, 3));
    const view = inner(el);
    const first = cards(el);
    expect(first).toHaveLength(1);

    el.events = all.slice(0, 4);
    await settle(el);
    expect(inner(el)).toBe(view);
    const next = cards(el);
    expect(next).toHaveLength(2);
    expect(next[0]).toBe(first[0]);
  });

  it('starts over for another transcript, and for one that does not start with the last', async () => {
    const a = [launch(1), tool('c1', '/w/a.json')];
    const el = await mount(a);
    const view = inner(el);

    el.events = [launch(2), tool('c9', '/w/b.json')];
    await settle(el);
    expect(inner(el)).not.toBe(view);
    expect(cards(el)).toHaveLength(1);

    const shorter = el.events.slice(0, 1);
    const other = inner(el);
    el.events = shorter;
    await settle(el);
    expect(inner(el)).not.toBe(other);
    expect(cards(el)).toHaveLength(0);
  });
});
