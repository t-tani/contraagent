// A transcript as the reader sees it: one round per launch, each a list of
// items (chat bubbles, tool cards, notices). Pure: no DOM. The model is
// mutated in place as pages of events arrive; the element re-renders it.
import { knownEvent, type LaunchEvent, type TranscriptEvent } from '@contraagent/api';
import type { RoundInfo, TryResult } from '../../events.js';
import { firstLine } from '../../lib/format.js';

/** Who ran a round: the coding agent (the CLI), the model and the role. */
export interface Who {
  agent: string;
  model: string;
  role: string;
}

const AGENT_NAMES: Record<string, string> = {
  claude: 'Claude Code',
  omp: 'omp',
  codex: 'Codex',
  opencode: 'opencode',
  gemini: 'Gemini CLI',
};

/** The display name of a coding agent's executable (`/usr/bin/claude` -> `Claude Code`). */
export function agentLabel(exe: string | null | undefined): string {
  const b = String(exe || '').split('/').pop() ?? '';
  return AGENT_NAMES[b] ?? b;
}

const argvFlag = (argv: readonly string[], name: string): string => {
  const i = argv.indexOf(name);
  return i >= 0 ? (argv[i + 1] ?? '') : '';
};

/** Who ran a launch: its argv names the agent and model, its prompt's TELEMETRY line the role. */
export function launchWho(launch: Pick<LaunchEvent, 'argv' | 'prompt'>): Who {
  const argv = launch.argv;
  const tele = /TELEMETRY [^\n]*role=([\w:-]+)/.exec(launch.prompt || '');
  const role = tele?.[1];
  return {
    agent: agentLabel(argv[0]),
    model: argvFlag(argv, '--model') || argvFlag(argv, '-m'),
    role: role && role !== '-' ? role : '',
  };
}

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

// --- rounds as the reader counts them --------------------------------------
//
// Each round is one turn of the coding agent. A *try* starts a new session
// (the first one, or a retry after a failure); a *fix-up* continues the same
// session after the output failed its checks, with the errors in its prompt; a
// *model switch* starts a session on the next model of the failover chain
// within the same try (the journal row's `hops`), after a rate limit.

/** The start of the prompt the runner sends when an output failed its checks (contracts.py). */
const FIXUP_PROMPT = 'The output file(s) you wrote do not pass their checks.';

/** The check errors a fix-up's prompt lists (the lines under `Errors:`). */
export function fixupErrors(prompt: string | null | undefined): string[] {
  const out: string[] = [];
  let inErrors = false;
  for (const line of (prompt || '').split('\n')) {
    if (/^Errors:\s*$/.test(line)) inErrors = true;
    else if (inErrors && line.startsWith('- ')) out.push(line.slice(2));
    else if (inErrors && line.trim() && !line.startsWith('- ')) inErrors = false;
  }
  return out;
}

export const isFixup = (launch: Pick<LaunchEvent, 'prompt'> | null | undefined): boolean =>
  !!launch && (launch.prompt || '').startsWith(FIXUP_PROMPT);


/**
 * Classify each round (by its launch) as a try or a fix-up, and attach what is known of
 * its result. `rows` are the task's journal rows in order; the n-th that ran is the n-th try's.
 */
export function classifyRounds(launches: readonly (Pick<LaunchEvent, 'prompt'> | null)[], rows: readonly TryResult[]): RoundInfo[] {
  // The tries that ran, in order: a resumed run numbers a task's attempts from 0 again,
  // so a try's row is found by its place, not by its attempt number.
  const byTry = new Map(rows.filter((r) => r.stop !== 'invalid_input' && r.stop !== 'skipped').map((r, i) => [i + 1, r]));
  const out: RoundInfo[] = [];
  let tryNo = 0;
  let fixupNo = 0;
  let hopNo = 0;
  launches.forEach((l, i) => {
    const hops = byTry.get(tryNo)?.hops?.length ?? 1;
    if (i > 0 && isFixup(l)) fixupNo++;
    else if (i > 0 && hopNo + 1 < hops) {
      hopNo++; // a fresh session within the same try: the next model of its chain
      fixupNo = 0;
    } else {
      tryNo++;
      hopNo = 0;
      fixupNo = 0;
    }
    const hop = byTry.get(tryNo)?.hops?.[hopNo];
    const model = hop?.model || hop?.route || '';
    const kind = fixupNo ? 'fixup' : hopNo ? 'switch' : 'try';
    out.push({ kind, tryNo, fixupNo, hopNo, model, result: null, rejectedWith: [], switchedStop: '', switchedTo: '', row: null });
  });
  out.forEach((r, i) => {
    const next = out[i + 1];
    if (next && next.tryNo === r.tryNo && next.hopNo !== r.hopNo) {
      r.result = 'switched';
      r.switchedStop = byTry.get(r.tryNo)?.hops?.[r.hopNo]?.stop ?? '';
      r.switchedTo = next.model;
      return;
    }
    if (next && next.tryNo === r.tryNo) {
      r.result = 'rejected';
      r.rejectedWith = fixupErrors(launches[i + 1]?.prompt);
      return;
    }
    const row = byTry.get(r.tryNo) ?? null;
    r.row = row;
    r.result = row ? (row.ok ? 'ok' : 'failed') : null;
  });
  return out;
}

/** The check name in an error line (`.../delta.json: [three_points] points: ...` -> `three_points`). */
export const checkName = (error: string): string => /\[([\w.-]+)\]/.exec(error)?.[1] ?? '';

/** A check error as the reader reads it: `[three_points] points: ...` after a path -> `three_points: points: ...`. */
export function checkMessage(error: string): string {
  const m = /\[([\w.-]+)\]\s*(.*)$/.exec(error);
  return m ? `${m[1]}: ${m[2]}` : error;
}

// --- web search results ------------------------------------------------------

/** One page a web search returned. */
export interface WebResult {
  title: string;
  url: string;
}

const RESULTS_MAX = 20;
const JSON_LINK = /\{\s*"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"url"\s*:\s*"(https?:\/\/[^"\s]+)"/g;
const NUMBERED = /^\s*\[\d+\]\s+(.+)\n\s*(https?:\/\/\S+)/gm;
const BARE_URL = /https?:\/\/[^\s"'<>)\]]+/g;

/**
 * The pages a web search's output lists, in order, at most 20: Claude Code's
 * `{"title", "url"}` links, omp's `[n] title` lines followed by a URL, else every
 * http(s) URL in the text (titled by itself).
 */
export function webResults(out: string | null | undefined): WebResult[] {
  const text = out ?? '';
  const found: WebResult[] = [];
  const seen = new Set<string>();
  const add = (title: string, url: string): void => {
    if (seen.has(url) || found.length >= RESULTS_MAX) return;
    seen.add(url);
    found.push({ title: title.trim() || url, url });
  };
  for (const m of text.matchAll(JSON_LINK)) {
    let title = m[1] ?? '';
    try {
      title = JSON.parse(`"${title}"`) as string;
    } catch {
      // an escape JSON does not take: the raw text is still a title
    }
    add(title, m[2] ?? '');
  }
  if (!found.length) for (const m of text.matchAll(NUMBERED)) add(m[1] ?? '', m[2] ?? '');
  if (!found.length) for (const m of text.matchAll(BARE_URL)) add('', m[0].replace(/[.,;:!?]+$/, '')); // a sentence's own punctuation
  return found;
}
