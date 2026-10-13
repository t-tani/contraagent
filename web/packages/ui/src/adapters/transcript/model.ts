// A transcript as the reader sees it: one round per launch, each a list of
// items (chat bubbles, tool cards, notices). Pure: no DOM. The model is
// mutated in place as pages of events arrive (`StreamController`);
// `transcriptSections` turns it into what `<cae-transcript>` shows.
import { knownEvent, type LaunchEvent, type TranscriptEvent } from '@contraagent/api';
import type { ToolCard, TranscriptItem } from '@contraagent/elements/transcript';
import { firstLine } from '../../words/format.js';
import { webResults } from './web.js';
import { launchWho, type Who } from './who.js';

/** One tool call: the card that opens on its start and receives its result. */
export interface ToolItem extends ToolCard {
  /** The call id pairing start and end; '' when the agent sent none. */
  call: string;
  /** The tool's short name (`bash`, `read`, ...). */
  icon: string;
  intent: string;
  /** The command shown in the card's body. */
  body: string;
}

/**
 * What a round shows, as `<cae-transcript>` takes it: the prompt the launch
 * assembled as the agent echoed it, assistant prose accumulated from its deltas
 * (`message`), a turn's closing thinking (`reasoning`), an API request the
 * coding agent sent again (`auto_retry_start`, an `event` whose `text` is the
 * error it got; its title is the reader's word, `transcriptSections`), a
 * notice, a tool call.
 */
export type Item = Exclude<TranscriptItem, ToolCard> | ToolItem;

export interface Round {
  id: string;
  /** The launch event that opened it; null for events that came before any launch. */
  launch: LaunchEvent | null;
  who: Who | null;
  items: Item[];
}

export interface Transcript {
  rounds: Round[];
  /** Tool cards by call id. omp reports one call in several event styles, sometimes twice: they all land in one card. */
  tools: Map<string, ToolItem>;
  next: number;
}

export const emptyTranscript = (): Transcript => ({ rounds: [], tools: new Map(), next: 0 });

const SESSION_MODEL = /session init:.*?model=([\w.\-:]+)/;

function newId(t: Transcript): string {
  return `i${t.next++}`;
}

function addRound(t: Transcript, launch: LaunchEvent | null): Round {
  const r: Round = { id: `r${t.rounds.length}`, launch, who: launch ? launchWho(launch) : null, items: [] };
  t.rounds.push(r);
  return r;
}

function currentRound(t: Transcript): Round {
  return t.rounds[t.rounds.length - 1] ?? addRound(t, null);
}

function setToolName(card: ToolItem, name: string | null | undefined): void {
  if (name) card.name = name;
  else if (!card.name) card.name = 'tool';
  card.icon = (card.name.split(/[_:]/).pop() ?? '').toLowerCase();
}

function cardFor(t: Transcript, round: Round, call: string): ToolItem {
  let c = call ? t.tools.get(call) : undefined;
  if (!c) {
    c = { type: 'tool', id: call ? `call:${call}` : newId(t), call, name: '', icon: '', summary: '', intent: '', body: '', output: null, status: 'running' };
    if (call) t.tools.set(call, c);
    round.items.push(c);
  }
  return c;
}

/**
 * Fold `events` into the transcript. Returns how many of them showed something
 * (a reader scrolled away is told that many arrived).
 */
export function applyEvents(t: Transcript, events: readonly TranscriptEvent[]): number {
  let shown = 0;
  for (const raw of events) {
    const e = knownEvent(raw);
    if (!e) continue;
    if (e.type === 'launch') {
      addRound(t, e);
      shown++;
      continue;
    }
    const r = currentRound(t);
    switch (e.type) {
      case 'message_start':
      case 'message_end':
        if (e.role !== 'user' || !e.text) continue;
        r.items.push({ type: 'prompt', id: newId(t), text: e.text });
        break;
      case 'turn_end':
        if (!e.thinking) continue;
        r.items.push({ type: 'reasoning', id: newId(t), text: e.thinking });
        break;
      case 'acall':
      case 'tool_execution_start':
      case 'tool_execution_update': {
        const c = cardFor(t, r, e.call);
        if (c.output === null) {
          setToolName(c, e.tool);
          c.summary = firstLine(e.cmd);
          c.intent = e.intent || '';
          c.body = e.cmd || c.body;
          if (e.web_query) c.query = e.web_query;
          if (e.web_fetch) c.page = e.web_fetch;
        } else if (!c.summary && e.cmd) {
          c.summary = firstLine(e.cmd); // a late duplicate may only add the summary
        }
        break;
      }
      case 'aresult':
      case 'tool_execution_end': {
        const c = cardFor(t, r, e.call);
        if (c.output !== null && !e.out) break; // a repeated, empty result must not blank the real one
        setToolName(c, e.tool);
        c.status = e.err ? 'error' : 'ok';
        if (!c.summary && c.body) c.summary = firstLine(c.body);
        c.output = e.out || '(no output)';
        if (c.query) c.links = webResults(c.output);
        break;
      }
      case 'message_update': {
        if (!e.delta) continue;
        const last = r.items[r.items.length - 1];
        if (last?.type === 'message') last.text += e.delta;
        else r.items.push({ type: 'message', id: newId(t), text: e.delta });
        break;
      }
      case 'auto_retry_start':
        r.items.push({ type: 'event', id: newId(t), icon: '↻', title: '', text: e.err ?? '' });
        break;
      case 'notice': {
        const model = SESSION_MODEL.exec(e.text || '')?.[1];
        if (model) {
          r.who ??= { agent: '', model: '', role: '' };
          if (!r.who.model) r.who.model = model;
        }
        r.items.push({ type: 'notice', id: newId(t), text: (e.text || '').replace(/\s+/g, ' ').trim() });
        break;
      }
    }
    shown++;
  }
  return shown;
}
