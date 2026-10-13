// A transcript as the reader sees it: one round per launch, each a list of
// items (chat bubbles, tool cards, notices). Pure: no DOM. The model is
// mutated in place as pages of events arrive (`StreamController`);
// `transcriptSections` turns it into what `<cae-transcript>` shows.
import { knownEvent, type LaunchEvent, type TranscriptEvent } from '@contraagent/api';
import { firstLine } from '../../words/format.js';
import { launchWho, type Who } from './who.js';

/** One tool call: the card that opens on its start and receives its result. */
export interface ToolItem {
  kind: 'tool';
  id: string;
  /** The call id pairing start and end; '' when the agent sent none. */
  call: string;
  name: string;
  /** The tool's short name, for its icon (`bash`, `read`, ...). */
  icon: string;
  /** One line: the command, pattern, path or URL. */
  preview: string;
  intent: string;
  /** The command shown in the card's body. */
  cmd: string;
  /** The query, when the call is a web search; '' otherwise. */
  webQuery: string;
  /** The URL, when the call reads a web page; '' otherwise. */
  webFetch: string;
  /** The result; null while the call runs. */
  out: string | null;
  status: 'run' | 'ok' | 'err';
}

export type Item =
  /** The prompt the launch assembled, as the agent echoed it. */
  | { kind: 'prompt'; id: string; text: string }
  /** Assistant prose, accumulated from its deltas. */
  | { kind: 'assistant'; id: string; raw: string }
  /** A turn's closing thinking. */
  | { kind: 'summary'; id: string; text: string }
  /** The coding agent sent an API request again (`auto_retry_start`), with the error it got. */
  | { kind: 'retry'; id: string; err: string }
  | { kind: 'notice'; id: string; text: string }
  | ToolItem;

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
    c = {
      kind: 'tool',
      id: call ? `call:${call}` : newId(t),
      call,
      name: '',
      icon: '',
      preview: '',
      intent: '',
      cmd: '',
      webQuery: '',
      webFetch: '',
      out: null,
      status: 'run',
    };
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
        r.items.push({ kind: 'prompt', id: newId(t), text: e.text });
        break;
      case 'turn_end':
        if (!e.thinking) continue;
        r.items.push({ kind: 'summary', id: newId(t), text: e.thinking });
        break;
      case 'acall':
      case 'tool_execution_start':
      case 'tool_execution_update': {
        const c = cardFor(t, r, e.call);
        if (c.out === null) {
          setToolName(c, e.tool);
          c.preview = firstLine(e.cmd);
          c.intent = e.intent || '';
          c.cmd = e.cmd || c.cmd;
          if (e.web_query) c.webQuery = e.web_query;
          if (e.web_fetch) c.webFetch = e.web_fetch;
        } else if (!c.preview && e.cmd) {
          c.preview = firstLine(e.cmd); // a late duplicate may only add the preview
        }
        break;
      }
      case 'aresult':
      case 'tool_execution_end': {
        const c = cardFor(t, r, e.call);
        if (c.out !== null && !e.out) break; // a repeated, empty result must not blank the real one
        setToolName(c, e.tool);
        c.status = e.err ? 'err' : 'ok';
        if (!c.preview && c.cmd) c.preview = firstLine(c.cmd);
        c.out = e.out || '(no output)';
        break;
      }
      case 'message_update': {
        if (!e.delta) continue;
        const last = r.items[r.items.length - 1];
        if (last?.kind === 'assistant') last.raw += e.delta;
        else r.items.push({ kind: 'assistant', id: newId(t), raw: e.delta });
        break;
      }
      case 'auto_retry_start':
        r.items.push({ kind: 'retry', id: newId(t), err: e.err ?? '' });
        break;
      case 'notice': {
        const model = SESSION_MODEL.exec(e.text || '')?.[1];
        if (model) {
          r.who ??= { agent: '', model: '', role: '' };
          if (!r.who.model) r.who.model = model;
        }
        r.items.push({ kind: 'notice', id: newId(t), text: (e.text || '').replace(/\s+/g, ' ').trim() });
        break;
      }
    }
    shown++;
  }
  return shown;
}
